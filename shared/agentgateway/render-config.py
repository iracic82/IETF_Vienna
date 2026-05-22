"""Render agentgateway config from per-sandbox env.

Reads AGENTS env var (comma-separated agent slugs) and emits the path-mode
config to stdout. Path layout matches the proven config.path.yaml from
DNS-AID/DEMO/agentgateway-2mcp/gateway/.

Per agent we emit two routes:
  POST /<slug>/mcp       → mcp backend pointing at fastmcp-<slug>:3000
  GET  /<slug>/cap.json  → http proxy to fastmcp-<slug>:3000 with urlRewrite

Cap-doc Pattern A (upstream serves, gateway proxies). Cap bytes are stable
because the FastMCP container bakes /app/cap.json at build time.

Env
  AGENTS              comma-separated agent slugs (e.g. "ip-reputation,url-scanner")
  ADMIN_ADDR          default 0.0.0.0:15000
  STATS_ADDR          default 0.0.0.0:15020
  READINESS_ADDR      default 0.0.0.0:15021
  LISTEN_PORT         default 3000

Usage (in Docker entrypoint)
  python /etc/agentgateway/render-config.py > /etc/agentgateway/config.yaml
  agentgateway -f /etc/agentgateway/config.yaml
"""

from __future__ import annotations

import os
import sys

AGENTS = [a.strip() for a in os.getenv("AGENTS", "").split(",") if a.strip()]
ADMIN_ADDR = os.getenv("ADMIN_ADDR", "0.0.0.0:15000")
STATS_ADDR = os.getenv("STATS_ADDR", "0.0.0.0:15020")
READINESS_ADDR = os.getenv("READINESS_ADDR", "0.0.0.0:15021")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "3000"))

if not AGENTS:
    print("AGENTS env var is required (comma-separated agent slugs)", file=sys.stderr)
    sys.exit(1)


def mcp_route(slug: str) -> str:
    return f"""\
          - name: {slug}-mcp
            matches:
              - path:
                  exact: /{slug}/mcp
            policies:
              cors:
                allowOrigins: ["*"]
                allowHeaders: [mcp-protocol-version, content-type, authorization]
                exposeHeaders: ["Mcp-Session-Id"]
            backends:
              - mcp:
                  targets:
                    - name: {slug}
                      mcp:
                        host: http://fastmcp-{slug}:3000/mcp
"""


def cap_route(slug: str) -> str:
    """Pattern B: gateway serves the cap doc inline via directResponse.

    No upstream HTTP call — the cap-sha256 is byte-stable so the no-churn
    property holds even if the FastMCP container restarts. Lab values are
    hard-coded; in production you'd template per-agent metadata in.
    """
    import json as _json
    cap_body = _json.dumps({
        "agent": slug,
        "version": "1.0.0",
        "protocol": "mcp",
        "transport": "streamable-http",
        "capabilities": [slug],
        "tools": [{"name": f"lookup_{slug.split('-')[0]}", "description": f"{slug} federation lookup"}],
        "auth": {"type": "none", "note": "lab demo"},
        "served_by": "agentgateway (Pattern B: inline directResponse)",
    }, indent=2)
    # Escape for YAML block scalar.
    cap_indent = "\n              ".join(cap_body.splitlines())
    return f"""\
          - name: {slug}-cap-v1
            matches:
              - path:
                  exact: /{slug}/cap.json
            policies:
              cors:
                allowOrigins: ["*"]
              directResponse:
                status: 200
                headers:
                  content-type: application/json
                body: |
                  {cap_indent}
"""


def render() -> str:
    routes = []
    for slug in AGENTS:
        routes.append(mcp_route(slug))
        routes.append(cap_route(slug))

    return f"""# yaml-language-server: $schema=https://agentgateway.dev/schema/config
#
# IETF_Vienna — threat-intel federation behind one agentgateway.
# Generated from AGENTS={','.join(AGENTS)}
#
# Path-mode routing (matches DNS-AID/DEMO/agentgateway-2mcp/gateway/config.path.yaml).
# SVCB record targets all point to this gateway; capability disambiguated by URL path.
#
# For each agent X we expose:
#   POST /X/mcp         → MCP proxy to fastmcp-X:3000/mcp
#   GET  /X/cap.json    → urlRewrite + proxy to fastmcp-X:3000/agent-cap.json

config:
  adminAddr: "{ADMIN_ADDR}"
  statsAddr: "{STATS_ADDR}"
  readinessAddr: "{READINESS_ADDR}"

binds:
  - port: {LISTEN_PORT}
    listeners:
      - name: ietf-vienna
        protocol: HTTP
        routes:
{''.join(routes)}"""


if __name__ == "__main__":
    sys.stdout.write(render())
