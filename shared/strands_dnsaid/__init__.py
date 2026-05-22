"""Strands wiring for the dns-aid MCP server.

Provides:
    make_agent(lab, slug, ...)   construct a Strands Agent with Vertex Claude
                                  and dns-aid tools pre-attached.
    run_session(lab, slug, fn)   open the MCP context, hand the live agent to
                                  fn, close cleanly on exit.

Usage (interactive, IETF2):
    from strands_dnsaid import run_session

    def loop(agent):
        while True:
            user = input("you> ")
            if user.lower() in {"exit", "quit"}:
                break
            print(agent(user))

    run_session(lab="ietf2", slug="a7c2f9d1", fn=loop)

Usage (one-shot, IETF):
    from strands_dnsaid import run_session

    run_session(
        lab="ietf",
        slug="a7c2f9d1",
        fn=lambda agent: print(agent("Is 185.220.101.45 malicious?")),
    )
"""

from __future__ import annotations

from .factory import make_agent, run_session
from .prompts import SYSTEM_PROMPTS

__all__ = ["make_agent", "run_session", "SYSTEM_PROMPTS"]
