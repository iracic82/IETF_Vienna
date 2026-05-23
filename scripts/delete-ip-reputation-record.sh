#!/usr/bin/env bash
# Delete the per-sandbox ip-reputation SVCB + TXT records.
# Run as student — needs sudo access to aws (lab sudoers grants this).
# Idempotent: missing records → no-op.
set -uo pipefail

source /opt/lab/lab.env 2>/dev/null || source /tmp/sandbox.env

: "${ROUTE53_ZONE_ID:?missing}"
: "${SANDBOX_SLUG:?missing}"
: "${ZONE:?missing}"

TARGET="_ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}."
echo "Target: ${TARGET}"

for KIND in SVCB TXT; do
    RRSET=$(sudo -H aws route53 list-resource-record-sets \
        --hosted-zone-id "${ROUTE53_ZONE_ID}" \
        --query "ResourceRecordSets[?Name=='${TARGET}'&&Type=='${KIND}'] | [0]")
    if [ "${RRSET}" = "null" ]; then
        echo "  - ${KIND}: not present (skip)"
        continue
    fi
    echo "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":${RRSET}}]}" > /tmp/del.json
    STATUS=$(sudo -H aws route53 change-resource-record-sets \
        --hosted-zone-id "${ROUTE53_ZONE_ID}" \
        --change-batch file:///tmp/del.json \
        --query 'ChangeInfo.Status' --output text)
    echo "  ✓ ${KIND}: ${STATUS}"
done
rm -f /tmp/del.json

echo ""
echo "Within ~5s the translator will remove the route from agentgateway."
echo "Verify with: curl http://localhost:3000/ip-reputation/mcp -X POST -H 'content-type:application/json' -d '{}'  # should 404"
