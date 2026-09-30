"""Jev-backed guardrail for agent tool calls.

An agent proposes a tool call. Before it runs, we ask Jev (a System One
decision model from TypeSafe) three typed questions about that call and
branch on the probabilities it returns. Jev cannot generate prose, so the
answer is always a number we can threshold, never text we have to parse.

Verdicts: "allow", "ask" (route to a human), "block".
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

JEV_ENDPOINT = os.environ.get("JEV_ENDPOINT", "https://openrouter.ai/api/v1/systemone")
JEV_MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-1.13")
JEV_TIMEOUT_SECS = float(os.environ.get("JEV_TIMEOUT_SECS", "5"))

# The three questions we ask Jev about every proposed tool call.
# Score criteria are ordered: index 0 is the safest, index 2 the most dangerous.
QUESTIONS: dict[str, Any] = {
    "risk": {
        "type": "score",
        "instructions": "How much damage can this tool call do if it is wrong?",
        "criteria": [
            "Read-only. Nothing changes.",
            "Changes state the user owns and can undo.",
            "Irreversible, destructive, or touches money, credentials, or other people's data.",
        ],
    },
    "intent_match": {
        "type": "noul",
        "instructions": "Does this tool call do what the user actually asked for, and nothing more?",
        "criteria": {
            "true": "The call is a direct, proportionate step toward the user's request.",
            "false": "The call goes beyond, contradicts, or is unrelated to the user's request.",
        },
    },
    "exfiltration": {
        "type": "noul",
        "instructions": "Does this tool call send private data, secrets, or files to an external destination?",
        "criteria": {
            "true": "It transmits secrets, credentials, personal data, or private files outside the system.",
            "false": "It does not move private data to an external destination.",
        },
    },
}


@dataclass(frozen=True)
class Policy:
    """Thresholds. Tune these on your own labelled tool calls, not on round numbers."""

    block_risk: float = 1.6       # score >= this and intent is weak -> block
    ask_risk: float = 1.0         # score >= this -> a human should look
    block_intent: float = 0.4     # intent probability below this -> block outright
    ask_intent: float = 0.7       # intent probability below this -> ask
    block_exfil: float = 0.6      # exfiltration probability >= this -> block

    @classmethod
    def from_env(cls) -> "Policy":
        def f(name: str, default: float) -> float:
            return float(os.environ.get(name, default))

        return cls(
            block_risk=f("POLICY_BLOCK_RISK", cls.block_risk),
            ask_risk=f("POLICY_ASK_RISK", cls.ask_risk),
            block_intent=f("POLICY_BLOCK_INTENT", cls.block_intent),
            ask_intent=f("POLICY_ASK_INTENT", cls.ask_intent),
            block_exfil=f("POLICY_BLOCK_EXFIL", cls.block_exfil),
        )


@dataclass
class Decision:
    verdict: str                 # allow | ask | block
    risk: float                  # 0..2, probability-weighted position on the risk scale
    intent_match: float          # 0..1
    exfiltration: float          # 0..1
    reasons: list[str]
    jev_model: str
    jev_cost_usd: float
    latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_state(user_request: str, tool_name: str, tool_args: dict[str, Any], context: str = "") -> dict[str, Any]:
    """The state Jev evaluates. Keep it small and factual. No instructions in here."""
    state: dict[str, Any] = {
        "user_request": user_request,
        "proposed_tool_call": {"tool": tool_name, "arguments": tool_args},
    }
    if context:
        state["agent_context"] = context
    return state


def call_jev(state: dict[str, Any], api_key: str, *, endpoint: str = JEV_ENDPOINT, model: str = JEV_MODEL) -> dict[str, Any]:
    """POST one decisions request to Jev via OpenRouter. Returns the raw JSON response."""
    payload = json.dumps({"model": model, "questions": QUESTIONS, "state": state}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rasik2002/jev-agent-guardrail",
            "X-Title": "jev-agent-guardrail",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=JEV_TIMEOUT_SECS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jev HTTP {e.code}: {body[:300]}") from e


def apply_policy(answers: dict[str, Any], policy: Policy) -> tuple[str, list[str]]:
    """Pure function: Jev answers -> (verdict, reasons). This is the part you unit test."""
    risk = float(answers["risk"]["score"])
    intent = float(answers["intent_match"]["noul"])
    exfil = float(answers["exfiltration"]["noul"])
    reasons: list[str] = []

    if exfil >= policy.block_exfil:
        reasons.append(f"exfiltration probability {exfil:.2f} >= {policy.block_exfil}")
        return "block", reasons
    if intent < policy.block_intent:
        reasons.append(f"intent match {intent:.2f} < {policy.block_intent}")
        return "block", reasons
    if risk >= policy.block_risk and intent < policy.ask_intent:
        reasons.append(f"risk {risk:.2f} >= {policy.block_risk} with weak intent {intent:.2f}")
        return "block", reasons
    if risk >= policy.ask_risk:
        reasons.append(f"risk {risk:.2f} >= {policy.ask_risk}")
    if intent < policy.ask_intent:
        reasons.append(f"intent match {intent:.2f} < {policy.ask_intent}")
    if reasons:
        return "ask", reasons
    reasons.append("low risk, clear intent, no exfiltration")
    return "allow", reasons


def decide(
    user_request: str,
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    api_key: str,
    context: str = "",
    policy: Policy | None = None,
    jev_caller=call_jev,
) -> Decision:
    """Full path: build state -> ask Jev -> apply policy -> Decision."""
    policy = policy or Policy.from_env()
    state = build_state(user_request, tool_name, tool_args, context)
    started = time.perf_counter()
    raw = jev_caller(state, api_key)
    latency_ms = int((time.perf_counter() - started) * 1000)
    answers = raw["answers"]
    verdict, reasons = apply_policy(answers, policy)
    return Decision(
        verdict=verdict,
        risk=float(answers["risk"]["score"]),
        intent_match=float(answers["intent_match"]["noul"]),
        exfiltration=float(answers["exfiltration"]["noul"]),
        reasons=reasons,
        jev_model=str(raw.get("model", JEV_MODEL)),
        jev_cost_usd=float(raw.get("usage", {}).get("cost", 0.0)),
        latency_ms=latency_ms,
    )
