# How Kiro was used on this project

This folder is the Kiro University Challenge deliverable. Each subfolder maps to a Kiro feature and to something real in the repo.

| Kiro feature | Where | What it did here |
|---|---|---|
| Steering | `steering/product.md`, `tech.md`, `structure.md` (always on), `writing.md` (fileMatch on `*.md`) | Locked the rules the agent had to follow: stdlib-only guardrail module, fail closed, key in SSM, least-privilege IAM, no em dashes in docs. The agent reads these every turn so I did not repeat them. |
| Specs | `specs/jev-guardrail/requirements.md`, `design.md`, `tasks.md` | Requirements in EARS form (WHEN / THEN / SHALL), a sequence diagram design, and a task list. Tasks 1 to 6 are done and map to the tests. Tasks 7 and 8 are the live verification and publish steps. |
| Hooks | `hooks/test-on-save.json` (PostFileSave: pytest on `.py`, `sam validate` on `template.yaml`), `hooks/secret-guard.json` (PreToolUse agent hook on writes) | Tests and template lint run automatically on save. The secret guard checks every write for key-shaped strings before it lands. |
| Custom agent | `agents/guardrail-reviewer.json` | A read-only reviewer with a fixed checklist: fail-open paths, secrets, IAM scope, Decimal conversion, question criteria. Deny rules on fs_write and shell so it cannot change anything. |
| MCP | `settings/mcp.json` | AWS Documentation MCP server, used to check SAM `HttpApi` CORS syntax, DynamoDB TTL attribute rules, and the SSM `GetParameter` ARN format while writing `template.yaml`. |
| Vibe session | (this README, the blog draft) | Exploratory Q&A to compare Jev against an LLM-as-judge for this use case before committing to the design. |

First commit date is after 2026-09-21, as the challenge requires.
