#!/usr/bin/env bash
# IETF lab — sandbox bootstrap. Runs once on Instruqt sandbox start.
#
# Order:
#   1. Render CoreDNS config from templates.
#   2. Register this sandbox's gateway IP + SVCB records in Route 53.
#   3. docker compose up.
set -euo pipefail

: "${SANDBOX_SLUG:?must be set by Instruqt random_id}"
export ZONE="${ZONE:-workshop.highvelocitynetworking.com}"
export AGENTS="ip-reputation"            # IETF lab uses ONE capability

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

# 1. CoreDNS — we let it forward to public resolvers; no local hostname
#    overrides needed for IETF (traffic to gw.${SLUG} can hairpin via VM IP).
export AGENTGATEWAY_IP="0.0.0.0"   # unused in IETF; present for shared script
"${SHARED}/coredns/render-corefile.sh" "${SHARED}/coredns/rendered"

# 2. Route 53 — register gateway IP + SVCB for the one IETF agent.
"${SHARED}/dns-seed/bootstrap.sh"

# 3. Bring up containers.
cd "${HERE}"
docker compose up -d --build

echo
echo "── IETF sandbox up ────────────────────────────────────────────────"
echo "  Subdomain: ${SANDBOX_SLUG}.${ZONE}"
echo "  Gateway:   gw.${SANDBOX_SLUG}.${ZONE}  →  port 3000"
echo "  Visualizer: http://localhost:8080  (DNS-AID Explorer)"
echo
echo "Try it:"
echo "  docker exec -it strands-agent python -m agent"
echo "  > Is 185.220.101.45 malicious?"
echo "────────────────────────────────────────────────────────────────────"
