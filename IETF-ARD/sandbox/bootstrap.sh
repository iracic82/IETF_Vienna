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

# Load AWS creds from the canonical boto3 location (NOT shell env) so
# docker compose can interpolate them into container env at compose-up
# time. They die with this shell — student shell never sees them.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -r /root/.aws/credentials ]; then
    AWS_ACCESS_KEY_ID=$(awk -F' *= *' '/aws_access_key_id/ {print $2; exit}' /root/.aws/credentials)
    AWS_SECRET_ACCESS_KEY=$(awk -F' *= *' '/aws_secret_access_key/ {print $2; exit}' /root/.aws/credentials)
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
fi
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Render CoreDNS config (forwards to public; agent traffic stays in docker net).
export AGENTGATEWAY_IP="0.0.0.0"
"${SHARED}/coredns/render-corefile.sh" "${SHARED}/coredns/rendered"

# Render agentgateway config on the host (matches DEMO/agentgateway-2mcp
# pattern — image used as-is, config mounted via docker volume).
export AGENTS="${AGENTS:-ip-reputation}"
mkdir -p "${SHARED}/agentgateway/rendered"
python3 "${SHARED}/agentgateway/render-config.py" > "${SHARED}/agentgateway/rendered/config.yaml"
echo "[bootstrap] rendered agentgateway config:"
head -20 "${SHARED}/agentgateway/rendered/config.yaml" | sed 's/^/  /'

# Bring up containers.
cd "${HERE}"
docker compose up -d

echo
echo "── IETF sandbox containers up ───────────────────────────────────"
echo "  Subdomain:  ${SANDBOX_SLUG}.${ZONE}"
echo "  Gateway:    http://localhost:3000 (xDS-driven — 0 routes until DNS is published)"
echo "  Translator: poll Route 53 every 5s for SVCB under the subdomain"
echo "  Visualizer: http://localhost:8080  (DNS-AID Explorer)"
echo
echo "  DNS-AID records are NOT published yet — that's challenge 2."
echo "  Publish via dns-aid (NOTE: --endpoint must be the backend container,"
echo "  not agentgateway, so the translator gets the correct backend host):"
echo "      source /opt/lab/lab.env"
echo "      dns-aid publish \\"
echo "          --name ip-reputation \\"
echo "          --domain \"\${SANDBOX_SLUG}.\${ZONE}\" \\"
echo "          --protocol mcp \\"
echo "          --endpoint fastmcp-ip-reputation \\"
echo "          --port 3000 \\"
echo "          --transport streamable-http \\"
echo "          --capability ip-reputation \\"
echo "          --cap-uri \"\${CAP_BASE_URL}/ip-reputation/v1.json\" \\"
echo "          --policy-uri \"\${CAP_BASE_URL}/ip-reputation/policy.json\""
echo "─────────────────────────────────────────────────────────────────"
