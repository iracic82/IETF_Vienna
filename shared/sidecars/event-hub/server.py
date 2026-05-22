"""Event hub — central pubsub for the DNS-AID Explorer visualizer.

One container, two endpoints:

  POST /events
      Accept a JSON event from any source (FastMCP server, dns-aid tracer,
      CoreDNS tailer, agentgateway tailer). Body is stored in a ring buffer
      and broadcast to all SSE subscribers.

      Body shape (loose):
        {
          "source":  "mcp:ip-reputation" | "dns-aid" | "coredns" | "agentgateway",
          "kind":    "tools_call" | "dns_query" | "dns_response" | "gateway_route" | ...,
          "ts":      epoch seconds float,
          ...source-specific fields...
        }

  GET  /stream
      Server-Sent Events stream of all events as they arrive. Used by the
      DNS-AID Explorer Next.js app.

  GET  /events?since=N
      JSON dump of the last N events (default 100). Used by Replay mode.

Stdlib only — no FastAPI, no flask, fits in one tiny container.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

RING_SIZE = int(os.getenv("RING_SIZE", "1000"))
PORT = int(os.getenv("PORT", "8888"))

_buffer: deque[dict] = deque(maxlen=RING_SIZE)
_subscribers: list[list] = []  # list of per-subscriber queues (also deques)
_lock = threading.Lock()


def publish(event: dict) -> None:
    with _lock:
        _buffer.append(event)
        for q in _subscribers:
            q.append(event)


def subscribe() -> list:
    q: list = []
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: list) -> None:
    with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _write_json(self, code: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/events":
            self._write_json(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            self._write_json(400, {"error": "invalid_json"})
            return

        evt.setdefault("ts", time.time())
        publish(evt)
        self._write_json(202, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/stream":
            self._serve_sse()
            return

        if parsed.path == "/events":
            qs = parse_qs(parsed.query)
            n = int(qs.get("since", ["100"])[0])
            with _lock:
                slice_ = list(_buffer)[-n:]
            self._write_json(200, slice_)
            return

        if parsed.path == "/healthz":
            self._write_json(200, {"ok": True, "buffered": len(_buffer)})
            return

        self._write_json(404, {"error": "not_found"})

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = subscribe()
        try:
            # Replay last 50 events on connect so the viz has context.
            with _lock:
                for evt in list(_buffer)[-50:]:
                    self._sse_send(evt)
            # Stream new events.
            while True:
                if q:
                    evt = q.pop(0)
                    self._sse_send(evt)
                else:
                    # Keep-alive comment every 15s.
                    time.sleep(0.05)
                    if int(time.time()) % 15 == 0:
                        try:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                        except BrokenPipeError:
                            return
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            unsubscribe(q)

    def _sse_send(self, evt: dict) -> None:
        try:
            payload = json.dumps(evt).encode()
            self.wfile.write(b"data: " + payload + b"\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise


def main() -> None:
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[event-hub] listening on :{PORT}  ring={RING_SIZE}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
