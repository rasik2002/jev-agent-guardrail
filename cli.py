"""Score one tool call from the terminal without deploying anything.

Usage:
  set OPENROUTER_API_KEY=sk-or-...
  python cli.py "clean up my downloads" shell '{"command": "rm -rf ~/Downloads"}'
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from guardrail import decide  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set")
        return 2
    user_request, tool = argv[0], argv[1]
    args = json.loads(argv[2]) if len(argv) > 2 else {}
    context = argv[3] if len(argv) > 3 else ""
    d = decide(user_request, tool, args, api_key=api_key, context=context)
    print(json.dumps(d.to_dict(), indent=2))
    return 0 if d.verdict == "allow" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
