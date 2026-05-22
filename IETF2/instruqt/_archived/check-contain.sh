#!/usr/bin/env bash
set -uo pipefail

: "${SANDBOX_SLUG:?}"
NAME="_threat-feed._mcp._agents.${SANDBOX_SLUG}.workshop.highvelocitynetworking.com"

RESULT=$(dig +short @127.0.0.1 SVCB "${NAME}" 2>&1 || true)

if echo "${RESULT}" | grep -qi "NXDOMAIN" || [ -z "${RESULT}" ]; then
    echo "✓ threat-feed is NXDOMAIN at local resolver"
    exit 0
fi

echo "✗ threat-feed still resolves: ${RESULT}"
exit 1
