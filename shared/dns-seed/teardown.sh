#!/usr/bin/env bash
# Remove this sandbox's DNS-AID records via dns-aid CLI + remove the
# gateway A record via aws. Best-effort.
set -uo pipefail

: "${SANDBOX_SLUG:?must be set}"
: "${AGENTS:?must be set}"
: "${ZONE:?must be set}"
: "${HOSTED_ZONE_ID:?must be set}"
export DNS_AID_BACKEND="${DNS_AID_BACKEND:-route53}"
export DNS_AID_ROUTE53_HOSTED_ZONE_ID="${HOSTED_ZONE_ID}"

SUBDOMAIN="${SANDBOX_SLUG}.${ZONE}"
GW_HOST="gw.${SUBDOMAIN}"
DNS_AID="${DNS_AID_VENV:-/opt/dns-aid-venv}/bin/dns-aid"

IFS=',' read -ra AGENT_LIST <<< "${AGENTS}"
for agent in "${AGENT_LIST[@]}"; do
    agent="${agent// /}"
    [ -z "${agent}" ] && continue
    "${DNS_AID}" delete --name "${agent}" --domain "${SUBDOMAIN}" --protocol mcp || true
done

# Best-effort A record cleanup.
aws route53 change-resource-record-sets \
    --hosted-zone-id "${HOSTED_ZONE_ID}" \
    --change-batch "$(cat <<EOF
{
  "Changes": [{
    "Action": "DELETE",
    "ResourceRecordSet": {
      "Name": "${GW_HOST}.",
      "Type": "A",
      "TTL": 60,
      "ResourceRecords": [{"Value": "0.0.0.0"}]
    }
  }]
}
EOF
)" >/dev/null 2>&1 || true

echo "[teardown] sandbox=${SANDBOX_SLUG} records removed (best-effort)."
