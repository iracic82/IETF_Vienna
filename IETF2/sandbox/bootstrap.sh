#!/usr/bin/env bash
# IETF2 lab — bring up containers only. DNS publishing left for the
# student via dns-aid CLI in the workshop challenges.
set -euo pipefail

: "${SANDBOX_SLUG:?must be set by Instruqt random_id}"
export ZONE="${ZONE:-iracictechguru.com}"
export AGENTS="${AGENTS:-ip-reputation,url-scanner,file-hash,cve-lookup,domain-age,asn-info,passive-dns,threat-feed}"

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

export AGENTGATEWAY_IP="0.0.0.0"
"${SHARED}/coredns/render-corefile.sh" "${SHARED}/coredns/rendered"

# Render agentgateway config on host (mounted as volume into the image).
mkdir -p "${SHARED}/agentgateway/rendered"
python3 "${SHARED}/agentgateway/render-config.py" > "${SHARED}/agentgateway/rendered/config.yaml"
echo "[bootstrap] rendered agentgateway config:"
head -20 "${SHARED}/agentgateway/rendered/config.yaml" | sed 's/^/  /'

cd "${HERE}"
docker compose up -d

echo
echo "── IETF2 sandbox containers up ──────────────────────────────────"
echo "  Subdomain:  ${SANDBOX_SLUG}.${ZONE}"
echo "  Federation: 7 legit + 1 rogue (threat-feed) backend containers"
echo "  Visualizer: http://localhost:8080"
echo
echo "DNS records NOT yet published — that's challenge 1's work via"
echo "dns-aid publish."
echo "─────────────────────────────────────────────────────────────────"
