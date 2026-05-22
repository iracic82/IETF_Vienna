"""IETF lab — Strands agent entrypoint.

Interactive REPL. The system prompt (in shared/strands_dnsaid/prompts.py)
already tells the agent how to discover and invoke the ip-reputation
capability via DNS-AID + agentgateway.

Stage flow (~12 min):
    student> Is 185.220.101.45 malicious?
    agent  > [discovers via DNS-AID] [verifies DNSSEC + JWS]
              [calls through gateway] [returns verdict + audit trail]
"""

from __future__ import annotations

import os
import sys

from strands_dnsaid import run_session


def repl(agent) -> None:
    print()
    print("╭─────────────────────────────────────────────────────────────╮")
    print("│ DNS-AID Threat-Intel Demo                                   │")
    print("│ ────────────────────────                                    │")
    print("│ Try:  Is 185.220.101.45 malicious?                          │")
    print("│       What about 8.8.8.8?                                   │")
    print("│       Look up 185.234.72.19                                 │")
    print("│ Quit: exit                                                  │")
    print("╰─────────────────────────────────────────────────────────────╯")
    print()
    while True:
        try:
            line = input("analyst> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.lower() in {"exit", "quit", ":q"}:
            return
        try:
            response = agent(line)
            print(f"\nagent> {response}\n")
        except Exception as exc:  # surface errors to the student in lab settings
            print(f"\nagent> [error: {exc}]\n", file=sys.stderr)


def main() -> int:
    slug = os.environ["SANDBOX_SLUG"]
    run_session(lab="ietf", slug=slug, fn=repl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
