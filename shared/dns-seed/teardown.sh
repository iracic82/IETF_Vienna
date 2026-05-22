#!/usr/bin/env bash
# Sandbox teardown — remove this sandbox's records from Route 53. Runs once
# on sandbox stop. Idempotent (won't fail on already-deleted records when
# wrapped in trap || true at the caller).
set -euo pipefail

GATEWAY_IP=$(curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
    || echo "0.0.0.0")
export GATEWAY_IP

HERE="$(cd "$(dirname "$0")" && pwd)"
export ACTION=DELETE
python3 "${HERE}/render-records.py" | \
    aws route53 change-resource-record-sets \
        --hosted-zone-id "${HOSTED_ZONE_ID}" \
        --change-batch file:///dev/stdin \
        || true

echo "[teardown] sandbox=${SANDBOX_SLUG} records deleted (best-effort)."
