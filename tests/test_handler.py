"""Lambda handler tests. boto3 and Jev are stubbed so nothing leaves the machine."""

import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402


class FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


class FakeDDB:
    def __init__(self):
        self.table = FakeTable()

    def Table(self, name):
        return self.table


class FakeSSM:
    def get_parameter(self, Name, WithDecryption):
        return {"Parameter": {"Value": "fake-key"}}


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setenv("DECISIONS_TABLE", "decisions")
    fake_boto3 = types.SimpleNamespace(resource=lambda *_: FakeDDB(), client=lambda *_: FakeSSM())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    sys.modules.pop("app", None)
    import app  # noqa: E402

    return app


def event(body):
    return {"body": json.dumps(body)}


def test_rejects_bad_json(handler):
    r = handler.lambda_handler({"body": "{not json"}, None)
    assert r["statusCode"] == 400


def test_rejects_missing_fields(handler):
    r = handler.lambda_handler(event({"tool": "shell"}), None)
    assert r["statusCode"] == 400


def test_happy_path_logs_to_dynamodb(handler, monkeypatch):
    def fake_decide(user_request, tool, arguments, *, api_key, context, policy):
        from guardrail import Decision

        return Decision("allow", 0.1, 0.95, 0.0, ["ok"], "typesafe/jev-1.13", 0.00001, 42)

    monkeypatch.setattr(handler, "decide", fake_decide)
    r = handler.lambda_handler(event({"user_request": "ls", "tool": "shell", "arguments": {"command": "ls"}, "session_id": "s1"}), None)
    assert r["statusCode"] == 200
    body = json.loads(r["body"])
    assert body["verdict"] == "allow"
    assert "decision_id" in body
    item = handler._ddb.table.items[0]
    assert item["session_id"] == "s1"
    assert item["expires_at"] > item["created_at"]
    # floats must have been converted for DynamoDB
    assert type(item["risk"]).__name__ == "Decimal"


def test_jev_failure_fails_closed_to_ask(handler, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Jev HTTP 503")

    monkeypatch.setattr(handler, "decide", boom)
    r = handler.lambda_handler(event({"user_request": "x", "tool": "shell", "arguments": {}}), None)
    assert r["statusCode"] == 502
    assert json.loads(r["body"])["verdict"] == "ask"
