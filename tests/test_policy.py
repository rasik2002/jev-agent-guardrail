"""Policy is a pure function of Jev's answers, so we test it without the network."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from guardrail import Policy, apply_policy, build_state, decide  # noqa: E402


def answers(risk: float, intent: float, exfil: float) -> dict:
    return {
        "risk": {"type": "score", "score": risk},
        "intent_match": {"type": "noul", "noul": intent},
        "exfiltration": {"type": "noul", "noul": exfil},
    }


P = Policy()


def test_read_only_clear_intent_allows():
    verdict, reasons = apply_policy(answers(0.1, 0.95, 0.01), P)
    assert verdict == "allow"
    assert reasons == ["low risk, clear intent, no exfiltration"]


def test_exfiltration_blocks_even_when_intent_is_high():
    verdict, reasons = apply_policy(answers(0.2, 0.9, 0.8), P)
    assert verdict == "block"
    assert "exfiltration" in reasons[0]


def test_unrelated_call_blocks():
    verdict, _ = apply_policy(answers(0.5, 0.2, 0.0), P)
    assert verdict == "block"


def test_destructive_with_weak_intent_blocks():
    verdict, reasons = apply_policy(answers(1.9, 0.6, 0.0), P)
    assert verdict == "block"
    assert "weak intent" in reasons[0]


def test_destructive_with_strong_intent_asks_not_blocks():
    verdict, _ = apply_policy(answers(1.9, 0.95, 0.0), P)
    assert verdict == "ask"


def test_medium_risk_asks():
    verdict, _ = apply_policy(answers(1.2, 0.9, 0.0), P)
    assert verdict == "ask"


def test_policy_from_env(monkeypatch):
    monkeypatch.setenv("POLICY_ASK_RISK", "1.5")
    assert Policy.from_env().ask_risk == 1.5
    assert apply_policy(answers(1.2, 0.9, 0.0), Policy.from_env())[0] == "allow"


def test_build_state_has_no_instructions():
    state = build_state("do x", "shell", {"command": "ls"}, context="ctx")
    assert set(state) == {"user_request", "proposed_tool_call", "agent_context"}
    assert state["proposed_tool_call"] == {"tool": "shell", "arguments": {"command": "ls"}}


def test_decide_uses_injected_caller_and_reads_usage():
    def fake_jev(state, api_key):
        assert api_key == "k"
        assert state["proposed_tool_call"]["tool"] == "shell"
        return {"answers": answers(0.0, 0.99, 0.0), "model": "typesafe/jev-1.13-test", "usage": {"cost": 0.00002}}

    d = decide("list files", "shell", {"command": "ls"}, api_key="k", jev_caller=fake_jev)
    assert d.verdict == "allow"
    assert d.jev_model == "typesafe/jev-1.13-test"
    assert d.jev_cost_usd == pytest.approx(0.00002)
    assert d.to_dict()["verdict"] == "allow"
