#!/usr/bin/env bash
# Publish this sandbox's DNS-AID records via the official dns-aid CLI.
#
# Uses https://github.com/infobloxopen/dns-aid-core — installed by the
# parent setup-host into a venv at /opt/dns-aid-venv. We just invoke
# `dns-aid publish` once per agent.
#
# Required env:
#   SANDBOX_SLUG, AGENTS, ZONE, HOSTED_ZONE_ID
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
#   DNS_AID_BACKEND=route53
set -euo pipefail

: "${SANDBOX_SLUG:?must be set}"
: "${AGENTS:?must be set}"
: "${ZONE:?must be set}"
: "${HOSTED_ZONE_ID:?must be set}"
export DNS_AID_BACKEND="${DNS_AID_BACKEND:-route53}"
export DNS_AID_ROUTE53_HOSTED_ZONE_ID="${HOSTED_ZONE_ID}"

# ── Resolve sandbox public IP (best effort). ─────────────────────────
# Try GCP external IP, then internal IP, then placeholder. The IP is
# only needed for the A record so `dig` returns something; agents inside
# the sandbox reach the gateway via the docker network directly.
GATEWAY_IP=$(curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
    2>/dev/null || true)
if [ -z "${GATEWAY_IP}" ]; then
    GATEWAY_IP=$(curl -s -H "Metadata-Flavor: Google" \
        "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip" \
        2>/dev/null || true)
fi
GATEWAY_IP="${GATEWAY_IP:-127.0.0.1}"
export GATEWAY_IP

# ── Build the per-sandbox subdomain. ─────────────────────────────────
SUBDOMAIN="${SANDBOX_SLUG}.${ZONE}"
GW_HOST="gw.${SUBDOMAIN}"

echo "[bootstrap] sandbox=${SANDBOX_SLUG}  ip=${GATEWAY_IP}  agents=${AGENTS}"
echo "[bootstrap] subdomain=${SUBDOMAIN}"
echo "[bootstrap] dns-aid backend=${DNS_AID_BACKEND}"

# ── Ensure dns-aid CLI is available. ─────────────────────────────────
DNS_AID="${DNS_AID_VENV:-/opt/dns-aid-venv}/bin/dns-aid"
if [ ! -x "${DNS_AID}" ]; then
    echo "[bootstrap] ERROR: dns-aid CLI not found at ${DNS_AID}" >&2
    echo "[bootstrap] setup-host should have created the venv and installed dns-aid." >&2
    exit 1
fi
"${DNS_AID}" --version 2>&1 | head -1

# ── Publish the gateway A record first via aws (dns-aid publish doesn't
#     manage simple A records — only DNS-AID-format SVCB/TXT records).
aws route53 change-resource-record-sets \
    --hosted-zone-id "${HOSTED_ZONE_ID}" \
    --change-batch "$(cat <<EOF
{
  "Comment": "IETF_Vienna gateway A record for ${SANDBOX_SLUG}",
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "${GW_HOST}.",
      "Type": "A",
      "TTL": 60,
      "ResourceRecords": [{"Value": "${GATEWAY_IP}"}]
    }
  }]
}
EOF
)" >/dev/null
echo "[bootstrap] gateway A: ${GW_HOST} → ${GATEWAY_IP}"

# ── Publish one DNS-AID record per agent via dns-aid CLI. ────────────
IFS=',' read -ra AGENT_LIST <<< "${AGENTS}"
for agent in "${AGENT_LIST[@]}"; do
    agent="${agent// /}"   # strip whitespace
    [ -z "${agent}" ] && continue
    echo "[bootstrap] publishing ${agent}"
    "${DNS_AID}" publish \
        --name "${agent}" \
        --domain "${SUBDOMAIN}" \
        --protocol mcp \
        --endpoint "${GW_HOST}" \
        --port 3000 \
        --version "1.0.0" \
        --capability "${agent}" \
        --description "Federation ${agent} capability (lab demo)" \
        || { echo "[bootstrap] ERROR: dns-aid publish failed for ${agent}" >&2; exit 1; }
done

echo "[bootstrap] all ${#AGENT_LIST[@]} agent record(s) published."
echo "[bootstrap] verify with:"
echo "    dig +short A    ${GW_HOST}"
echo "    dig +short SVCB _${AGENT_LIST[0]}._mcp._agents.${SUBDOMAIN}"
echo "    dns-aid discover ${SUBDOMAIN}"
