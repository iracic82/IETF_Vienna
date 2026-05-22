#!/usr/bin/env bash
# Sandbox bootstrap — register this sandbox's gateway IP and SVCB records
# in Route 53. Runs once on sandbox start (before docker-compose up).
#
# Required env (set by Instruqt sandbox.hcl):
#   SANDBOX_SLUG      from random_id.sandbox_slug.hex
#   AGENTS            comma-separated agent slugs for THIS lab
#   ZONE              workshop.highvelocitynetworking.com
#   HOSTED_ZONE_ID    Route 53 hosted zone ID for ZONE
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   IAM creds with Route53 change perms
set -euo pipefail

# Discover the VM's public IPv4 from GCP metadata.
GATEWAY_IP=$(curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip")
export GATEWAY_IP

echo "[bootstrap] sandbox=${SANDBOX_SLUG}  ip=${GATEWAY_IP}  agents=${AGENTS}"

# Render changeset and apply.
HERE="$(cd "$(dirname "$0")" && pwd)"
export ACTION=UPSERT
python3 "${HERE}/render-records.py" | \
    aws route53 change-resource-record-sets \
        --hosted-zone-id "${HOSTED_ZONE_ID}" \
        --change-batch file:///dev/stdin

echo "[bootstrap] Route53 changeset applied."
echo "[bootstrap] verify with:"
echo "    dig +short A   gw.${SANDBOX_SLUG}.${ZONE}"
echo "    dig +short SVCB _$(echo ${AGENTS} | cut -d, -f1)._mcp._agents.${SANDBOX_SLUG}.${ZONE}"
