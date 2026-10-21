"""Lambda handler: POST /guard

Request body:
{
  "user_request": "clean up my downloads folder",
  "tool": "shell",
  "arguments": {"command": "rm -rf ~/Downloads"},
  "context": "optional short agent context",
  "session_id": "optional, groups related calls"
}

Response: the Decision as JSON, plus a decision_id. Every decision is written
to DynamoDB so you can audit what your agent tried to do and what happened.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from typing import Any

import boto3

from guardrail import Policy, decide

TABLE_NAME = os.environ.get("DECISIONS_TABLE", "")
API_KEY_PARAM = os.environ.get("OPENROUTER_API_KEY_PARAM", "/jev-guardrail/openrouter-api-key")
LOG_TTL_DAYS = int(os.environ.get("LOG_TTL_DAYS", "30"))

# The demo UI, loaded once per container and served on GET /.
_UI_PATH = os.path.join(os.path.dirname(__file__), "index.html")
try:
    with open(_UI_PATH, encoding="utf-8") as _f:
        _UI_HTML = _f.read()
except OSError:
    _UI_HTML = "<h1>Jev Agent Guardrail</h1><p>POST a tool call to /guard.</p>"

# Module-level clients are reused across warm invocations.
_ddb = boto3.resource("dynamodb")
_ssm = boto3.client("ssm")
_api_key_cache: dict[str, str] = {}


def _api_key() -> str:
    """Read the OpenRouter key from SSM Parameter Store once per container."""
    if "key" not in _api_key_cache:
        value = _ssm.get_parameter(Name=API_KEY_PARAM, WithDecryption=True)["Parameter"]["Value"]
        _api_key_cache["key"] = value
    return _api_key_cache["key"]


def _to_ddb(obj: Any) -> Any:
    """DynamoDB rejects floats. Convert recursively to Decimal."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(v) for v in obj]
    return obj


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }


def _method(event: dict[str, Any]) -> str:
    """HTTP API (v2) puts the method under requestContext.http.method."""
    ctx = event.get("requestContext", {})
    return (ctx.get("http", {}) or {}).get("method", "") or event.get("httpMethod", "")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # GET serves the demo UI so a human can try the guardrail in a browser.
    if _method(event) == "GET":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": _UI_HTML,
        }

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "body must be JSON"})

    user_request = body.get("user_request")
    tool = body.get("tool")
    arguments = body.get("arguments", {})
    if not isinstance(user_request, str) or not isinstance(tool, str) or not isinstance(arguments, dict):
        return _response(400, {"error": "user_request (str), tool (str) and arguments (object) are required"})

    try:
        decision = decide(
            user_request,
            tool,
            arguments,
            api_key=_api_key(),
            context=str(body.get("context", ""))[:2000],
            policy=Policy.from_env(),
        )
    except Exception as e:  # noqa: BLE001 - fail closed, never fail open
        print(f"guardrail error: {e}")
        return _response(502, {"verdict": "ask", "error": "guardrail unavailable, defaulting to ask", "detail": str(e)[:200]})

    decision_id = str(uuid.uuid4())
    now = int(time.time())
    record = {
        "decision_id": decision_id,
        "created_at": now,
        "expires_at": now + LOG_TTL_DAYS * 86400,
        "session_id": str(body.get("session_id", "none"))[:256],
        "user_request": user_request[:2000],
        "tool": tool[:200],
        "arguments": json.dumps(arguments)[:4000],
        **decision.to_dict(),
    }
    if TABLE_NAME:
        _ddb.Table(TABLE_NAME).put_item(Item=_to_ddb(record))

    return _response(200, {"decision_id": decision_id, **decision.to_dict()})
