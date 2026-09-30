# Structure

```
jev-agent-guardrail/
├── template.yaml          SAM: HTTP API + Lambda + DynamoDB + IAM
├── src/
│   ├── guardrail.py       Jev client, QUESTIONS, Policy, apply_policy, decide  (stdlib only)
│   ├── app.py             Lambda handler: validate -> decide -> log to DynamoDB -> respond
│   └── requirements.txt   boto3 (Lambda deps only)
├── cli.py                 score one tool call from the terminal
├── examples/
│   └── agent_demo.py      scripted agent loop with the guardrail in front of every call
├── tests/
│   ├── test_policy.py     pure policy + decide with injected caller
│   └── test_handler.py    Lambda handler with stubbed boto3
├── requirements-dev.txt   pytest + boto3 for local tests
└── .kiro/                 steering, specs, hooks, agents, settings (see .kiro/README.md)
```

Conventions:
- New guardrail questions go in `QUESTIONS` in `guardrail.py` and get a matching branch in `apply_policy` plus a test in `test_policy.py`.
- Anything that touches AWS lives in `app.py` or `template.yaml`, never in `guardrail.py`.
- Examples must be runnable with only `OPENROUTER_API_KEY` set. No AWS needed to try the idea.
