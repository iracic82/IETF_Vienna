"""IETF2 lab — Strands agent for the incident-response workshop.

Multi-turn REPL. On start, the agent surfaces the HR email and offers to
begin the investigation. The system prompt (shared/strands_dnsaid/prompts.py)
covers the 4 challenge phases.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from strands_dnsaid import run_session


INBOX = Path("/app/inbox.md")


def banner() -> None:
    print()
    print("╭─────────────────────────────────────────────────────────────────╮")
    print("│ AcmeCorp SOC — Threat-Intel Federation Workshop                 │")
    print("│ Monday morning. You have one inbox message.                     │")
    print("╰─────────────────────────────────────────────────────────────────╯")
    if INBOX.exists():
        print()
        print(INBOX.read_text())
    print()
    print("Open the Instruqt panel for Challenge 1. Talk to your assistant in")
    print("this terminal. Open the DNS-AID Explorer tab to watch the protocol")
    print("flow live.")
    print()
    print("Type  'quit'  or Ctrl-D when done.")
    print()


def repl(agent) -> None:
    banner()
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
            print(f"\nassistant> {response}\n")
        except Exception as exc:
            print(f"\nassistant> [error: {exc}]\n", file=sys.stderr)


def main() -> int:
    slug = os.environ["SANDBOX_SLUG"]
    run_session(lab="ietf2", slug=slug, fn=repl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
