# Sidecars — event emission for the DNS-AID Explorer

Three event sources, one central hub.

```
       ┌─────────────────┐
       │ fastmcp-* agents│──┐  (built-in EVENT_SINK_URL hook)
       └─────────────────┘  │
       ┌─────────────────┐  │
       │ dns-aid-wrapper │──┤    POST /events
       └─────────────────┘  │
                            ▼
              ┌─────────────────────────┐
              │   event-hub (port 8888) │
              │   ring buffer + SSE     │
              └─────────────────────────┘
                            │
                            │  GET /stream  (SSE)
                            ▼
              ┌─────────────────────────┐
              │   DNS-AID Explorer      │  (Next.js app, ../viz)
              │   visualizer            │
              └─────────────────────────┘
```

## event-hub

Stdlib-only Python HTTP server. Three endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /events` | Accept event JSON from any sidecar |
| `GET  /stream` | Server-Sent Events; live tail to the visualizer |
| `GET  /events?since=N` | Last N events as JSON (for Replay mode) |

Configure with `EVENT_SINK_URL=http://event-hub:8888/events` on every source.

## dns-aid-wrapper

Transparent stdio tee that wraps `python -m dns_aid.mcp.server`. Strands
connects to the wrapper, the wrapper proxies to the real MCP server, and
on every JSON-RPC frame we POST a structured event to the hub.

Drop-in replacement in docker-compose:

```yaml
services:
  dns-aid-mcp:
    image: ietf-vienna/dns-aid-wrapper
    command: ["python", "-u", "/app/wrapper.py"]
    environment:
      EVENT_SINK_URL: http://event-hub:8888/events
```

## Deferred for v2

- **coredns-tailer** — tails CoreDNS log plugin output (JSON), re-emits to hub. Useful for surfacing DNSSEC AD flag arrivals.
- **gateway-tailer** — parses agentgateway access logs or scrapes Prometheus `:15020` and re-emits route-match events.

Both are nice-to-have. The FastMCP + dns-aid-wrapper combo already covers
the 9 demo steps for the IETF lab; CoreDNS/gateway events would add a
2-3 extra frames of detail.
