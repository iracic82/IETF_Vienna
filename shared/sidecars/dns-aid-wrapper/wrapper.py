"""Wraps `python -m dns_aid.mcp.server` and emits events to the event-hub.

The dns-aid MCP server uses stdio JSON-RPC. We sit between Strands and
dns-aid as a tee: forward bytes both ways untouched, but parse the
JSON-RPC envelopes and emit an event to the hub for every method/tool
call. Zero behavior change for the agent.

Run instead of the bare server in docker-compose:

    services:
      dns-aid-mcp:
        command: ["python", "-u", "/app/wrapper.py"]
        environment:
          EVENT_SINK_URL: http://event-hub:8888/events

Inside wrapper.py we spawn `python -m dns_aid.mcp.server` as a child and
pump stdin/stdout through.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

SINK = os.getenv("EVENT_SINK_URL", "")


def emit(kind: str, payload: dict) -> None:
    if not SINK:
        return
    body = json.dumps({"source": "dns-aid", "kind": kind, "ts": time.time(), **payload}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(SINK, data=body, headers={"Content-Type": "application/json"}),
            timeout=0.5,
        )
    except Exception:
        pass


def _try_parse(line: bytes) -> dict | None:
    """JSON-RPC messages are length-prefixed in real MCP stdio; for our
    purpose we accept either raw JSON lines OR length-prefixed framing.
    The wrapper is best-effort: if we can't parse, we still forward.
    """
    s = line.decode(errors="replace").strip()
    if not s or not s.startswith("{"):
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def pump(src, dst, kind: str) -> None:
    while True:
        chunk = src.readline()
        if not chunk:
            return
        dst.write(chunk)
        dst.flush()

        parsed = _try_parse(chunk)
        if not parsed:
            continue

        method = parsed.get("method")
        params = parsed.get("params") or {}
        if kind == "client_to_server" and method:
            evt: dict = {"direction": "request", "method": method}
            if method == "tools/call":
                evt["tool"] = params.get("name")
                evt["args"] = params.get("arguments")
            emit("rpc", evt)
        elif kind == "server_to_client" and "result" in parsed:
            evt = {"direction": "response", "id": parsed.get("id")}
            res = parsed["result"]
            if isinstance(res, dict):
                # tool result content arrives as {"content": [...]}
                content = res.get("content")
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and first.get("type") == "text":
                        evt["text_preview"] = (first.get("text") or "")[:240]
            emit("rpc", evt)


def main() -> int:
    child = subprocess.Popen(
        [sys.executable, "-m", "dns_aid.mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        bufsize=0,
    )

    if child.stdin is None or child.stdout is None:
        return 1

    t1 = threading.Thread(
        target=pump, args=(sys.stdin.buffer, child.stdin, "client_to_server"), daemon=True
    )
    t2 = threading.Thread(
        target=pump, args=(child.stdout, sys.stdout.buffer, "server_to_client"), daemon=True
    )
    t1.start()
    t2.start()

    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
