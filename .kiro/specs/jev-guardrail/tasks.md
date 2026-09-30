# Implementation Plan

- [x] 1. Core guardrail module
  - [x] 1.1 Define `QUESTIONS` (risk score, intent noul, exfiltration noul) with concrete criteria
  - [x] 1.2 `Policy` dataclass with env overrides
  - [x] 1.3 `build_state`, `call_jev` (urllib, timeout, HTTP error -> RuntimeError)
  - [x] 1.4 `apply_policy` pure function implementing the decision table
  - [x] 1.5 `decide` with injectable caller, latency and cost capture
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 3.x_

- [x] 2. Lambda handler
  - [x] 2.1 Input validation and 400 responses
  - [x] 2.2 SSM SecureString key read with per-container cache
  - [x] 2.3 Fail-closed 502 `ask` on any decide error
  - [x] 2.4 DynamoDB record with TTL and Decimal conversion
  - _Requirements: 1.1, 1.2, 4.x, 5.x, 6.1_

- [x] 3. Infrastructure (SAM)
  - [x] 3.1 HTTP API with CORS, POST /guard
  - [x] 3.2 Lambda python3.12 arm64 with env vars
  - [x] 3.3 DynamoDB on-demand, TTL, `by-session` GSI
  - [x] 3.4 Least-privilege IAM (single SSM ARN, table write only)
  - [x] 3.5 `sam validate --lint` passes
  - _Requirements: 5.2, 5.3, 6.2, 6.3, 7.3_

- [x] 4. Local developer tooling
  - [x] 4.1 `cli.py` scores one call
  - [x] 4.2 `examples/agent_demo.py` scripted agent loop
  - _Requirements: 7.2_

- [x] 5. Tests
  - [x] 5.1 Policy branch tests
  - [x] 5.2 Handler tests with stubbed boto3
  - [x] 5.3 All tests pass offline
  - _Requirements: 7.1_

- [x] 6. Docs
  - [x] 6.1 README with architecture, quick start, deploy, cost, design notes
  - [x] 6.2 `.kiro/README.md` explaining how each Kiro feature was used

- [ ] 7. Verification against live Jev
  - [ ] 7.1 Run `examples/agent_demo.py` with a real key, capture output for the blog
  - [ ] 7.2 Deploy with `sam deploy --guided`, curl the endpoint, capture the response
  - [ ] 7.3 Record demo video (30s to 3min) for Kiro University

- [ ] 8. Publish
  - [ ] 8.1 Push to github.com/rasik2002/jev-agent-guardrail (public)
  - [ ] 8.2 Submit Kiro University final exam form by Oct 5 23:59 PDT
  - [ ] 8.3 Blog: Builder Series Part 3 on AWS Builder Center + dev.to
  - [ ] 8.4 LinkedIn post with #KiroUniversity #BuildWithKiro tagging @kirodotdev
