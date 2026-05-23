"""Render agentgateway config for xDS-driven discovery mode.

The gateway has NO static routes. All Bind/Listener/Route/Backend
resources are pushed at runtime by the dns-aid translator over Envoy
v3 ADS (gRPC). The translator polls Route 53 for SVCB records under
the per-sandbox DNS-AID zone and reconciles the gateway state.

This config file only declares:
  - admin/stats/readiness ports
  - xdsAddress — where the gateway connects upstream for resources

Env
  XDS_ADDRESS         default http://translator:18000
  ADMIN_ADDR          default 0.0.0.0:15000
  STATS_ADDR          default 0.0.0.0:15020
  READINESS_ADDR      default 0.0.0.0:15021
"""

from __future__ import annotations

import os
import sys

XDS_ADDRESS = os.getenv("XDS_ADDRESS", "http://translator:18000")
ADMIN_ADDR = os.getenv("ADMIN_ADDR", "0.0.0.0:15000")
STATS_ADDR = os.getenv("STATS_ADDR", "0.0.0.0:15020")
READINESS_ADDR = os.getenv("READINESS_ADDR", "0.0.0.0:15021")


def render() -> str:
    return f"""# yaml-language-server: $schema=https://agentgateway.dev/schema/config
#
# IETF_Vienna — xDS-driven config.
# All routes/backends come from the dns-aid translator over ADS.
# Publishing a DNS-AID record creates a route; deleting the record
# removes it. No gateway restart, no static config edits.

config:
  adminAddr: "{ADMIN_ADDR}"
  statsAddr: "{STATS_ADDR}"
  readinessAddr: "{READINESS_ADDR}"
  xdsAddress: "{XDS_ADDRESS}"
"""


if __name__ == "__main__":
    sys.stdout.write(render())
