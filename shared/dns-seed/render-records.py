"""Render a Route 53 changeset JSON for ONE sandbox.

Reads SANDBOX_SLUG, GATEWAY_IP, AGENTS, GATEWAY_PORT from env and emits
the changeset on stdout. Wraps with action UPSERT for bootstrap, DELETE
for teardown.

Per sandbox we publish:
  gw.${SLUG}.workshop.hvn.com.                    A      <GATEWAY_IP>
  _index._agents.${SLUG}.workshop.hvn.com.       TXT    JSON list of agents
  _<agent>._mcp._agents.${SLUG}.workshop.hvn.com. SVCB   path-mode (target = gw.${SLUG})

Path-mode SVCB matches the proven config.path.yaml — one gateway target
shared by all this sandbox's capabilities; URL path disambiguates per
agent at the gateway.

Env
  SANDBOX_SLUG       e.g. "a7c2f9d1"  (from Instruqt random_id)
  GATEWAY_IP         public IPv4 of the sandbox VM (from GCP metadata)
  GATEWAY_PORT       default 3000 (matches agentgateway listener)
  AGENTS             comma-separated agent slugs
  ZONE               default "workshop.highvelocitynetworking.com"
  ACTION             "UPSERT" (bootstrap) or "DELETE" (teardown)
  TTL                default 60 (short for live updates)

Usage
  python render-records.py | aws route53 change-resource-record-sets \\
      --hosted-zone-id Z093585515KQI46NM8IF \\
      --change-batch file:///dev/stdin
"""

from __future__ import annotations

import json
import os
import sys

SLUG = os.environ["SANDBOX_SLUG"]
GW_IP = os.environ["GATEWAY_IP"]
GW_PORT = int(os.getenv("GATEWAY_PORT", "3000"))
AGENTS = [a.strip() for a in os.environ["AGENTS"].split(",") if a.strip()]
ZONE = os.getenv("ZONE", "workshop.highvelocitynetworking.com")
ACTION = os.getenv("ACTION", "UPSERT")
TTL = int(os.getenv("TTL", "60"))

GW_HOST = f"gw.{SLUG}.{ZONE}"


def svcb_value(agent: str) -> str:
    """Render an SVCB record value matching show_svcb.py --mode path output.

    Private-Use keys (RFC 9460 §14.3):
      key65400 = cap-uri      https://gw.${SLUG}/<agent>/cap.json
      key65401 = cap-sha256   (placeholder; gateway recomputes on each build)
      key65404 = environment  "workshop"
    """
    cap_uri = f"https://{GW_HOST}/{agent}/cap.json"
    # SVCB wire format Route 53 accepts: priority + target + alpn + port + keys
    return (
        f'1 {GW_HOST}. '
        f'alpn="mcp,h2" '
        f'port={GW_PORT} '
        f'key65400="{cap_uri}" '
        f'key65401="lab-cap-sha-placeholder" '
        f'key65404="workshop"'
    )


def index_txt() -> str:
    body = {
        "v": 1,
        "domain": f"{SLUG}.{ZONE}",
        "agents": [{"name": a, "protocol": "mcp"} for a in AGENTS],
    }
    return json.dumps(body, separators=(",", ":"))


def changes() -> list[dict]:
    out = []

    # 1. Gateway A record
    out.append(
        {
            "Action": ACTION,
            "ResourceRecordSet": {
                "Name": f"{GW_HOST}.",
                "Type": "A",
                "TTL": TTL,
                "ResourceRecords": [{"Value": GW_IP}],
            },
        }
    )

    # 2. Per-agent SVCB
    for agent in AGENTS:
        out.append(
            {
                "Action": ACTION,
                "ResourceRecordSet": {
                    "Name": f"_{agent}._mcp._agents.{SLUG}.{ZONE}.",
                    "Type": "SVCB",
                    "TTL": TTL,
                    "ResourceRecords": [{"Value": svcb_value(agent)}],
                },
            }
        )

    # 3. Index TXT
    out.append(
        {
            "Action": ACTION,
            "ResourceRecordSet": {
                "Name": f"_index._agents.{SLUG}.{ZONE}.",
                "Type": "TXT",
                "TTL": TTL,
                "ResourceRecords": [{"Value": f'"{index_txt()}"'}],
            },
        }
    )

    return out


def main() -> int:
    batch = {
        "Comment": f"IETF_Vienna {ACTION} for sandbox {SLUG} ({len(AGENTS)} agents)",
        "Changes": changes(),
    }
    json.dump(batch, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
