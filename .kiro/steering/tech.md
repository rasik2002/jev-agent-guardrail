# Tech

Stack:
- Python 3.12, standard library only in `src/guardrail.py` (urllib for HTTP). No requests, no httpx. Keeps the Lambda package tiny and the module importable anywhere.
- `boto3` only in `src/app.py` (Lambda handler). It ships in the Lambda runtime.
- AWS SAM for infrastructure. One `template.yaml`. Resources: HTTP API, Lambda (arm64), DynamoDB (on-demand, TTL, `by-session` GSI), SSM SecureString parameter read at runtime.
- Jev via OpenRouter: `POST https://openrouter.ai/api/v1/systemone`, model `typesafe/jev-1.13` pinned by default. Request shape: `{model, questions, state}`. Response: `{answers, model, usage}`.
- Tests: pytest. Network and boto3 are always stubbed. Tests must run offline.

Commands:
- `python -m pytest -q` runs all tests.
- `sam validate --lint` checks the template.
- `sam build && sam deploy --guided` deploys.
- `python cli.py "<request>" <tool> '<json args>'` scores one call locally.

Rules:
- `apply_policy` stays a pure function of Jev answers and a `Policy`. No I/O in it.
- Never put the OpenRouter key in code, env files committed to git, or the SAM template. It lives in SSM.
- IAM least privilege: Lambda gets `ssm:GetParameter` on one parameter ARN and write-only on one table.
- DynamoDB rejects floats. Convert to `Decimal` before `put_item` (see `_to_ddb`).
- Keep `QUESTIONS` criteria concrete and mutually exclusive. Jev quality depends on the criteria text more than anything else.
