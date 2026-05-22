#!/usr/bin/env bash
# IETF lab — bring up containers only. DNS publishing is intentionally
# left for the student to do via `dns-aid publish` in challenge 2.
#
# Required env (set by setup-host):
#   SANDBOX_SLUG, ZONE, HOSTED_ZONE_ID, AWS_*, DNS_AID_BACKEND
set -euo pipefail

: "${SANDBOX_SLUG:?must be set}"
: "${ZONE:?must be set}"

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

# Render CoreDNS config (forwards to public; agent traffic stays in docker net).
export AGENTGATEWAY_IP="0.0.0.0"
"${SHARED}/coredns/render-corefile.sh" "${SHARED}/coredns/rendered"

# Bring up containers. AGENTS only used by agentgateway to decide which
# backends to route — independent of whether DNS records are published.
export AGENTS="${AGENTS:-ip-reputation}"
cd "${HERE}"
docker compose up -d --build

echo
echo "── IETF sandbox containers up ───────────────────────────────────"
echo "  Subdomain:  ${SANDBOX_SLUG}.${ZONE}"
echo "  Gateway:    http://localhost:3000"
echo "  Visualizer: http://localhost:8080  (DNS-AID Explorer)"
echo
echo "  DNS-AID records are NOT published yet — that's challenge 2."
echo "  Source the env then run dns-aid publish:"
echo "      source /tmp/sandbox.env"
echo "      dns-aid publish -n ip-reputation -d \"\${SANDBOX_SLUG}.\${ZONE}\" \\"
echo "          -p mcp -e \"gw.\${SANDBOX_SLUG}.\${ZONE}\" --port 3000"
echo "─────────────────────────────────────────────────────────────────"
