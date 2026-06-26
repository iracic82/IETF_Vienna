"""IETF lab agent entrypoint — thin wrapper around agent_vertex.py.

The Strands+LiteLLM+Vertex path returns UNEXPECTED_TOOL_CALL on tool
invocations. agent_vertex.py uses vertexai.GenerativeModel directly,
which handles MCP-style tool schemas natively. This module simply
delegates so the assignment can keep saying `python /app/agent.py`.
"""

from __future__ import annotations

import runpy


def main() -> None:
    runpy.run_module("agent_vertex", run_name="__main__")


if __name__ == "__main__":
    main()
