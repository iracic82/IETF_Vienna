#!/usr/bin/env bash
# IETF2 lab — sandbox bootstrap. Publishes 8 SVCB records:
#   7 legit federation capabilities + 1 rogue threat-feed.
# The "tampered ip-reputation" wrinkle for Challenge 3 is implemented at
# the gateway routing layer (see docker-compose.yml comment).
set -euo pipefail

: "${SANDBOX_SLUG:?must be set by Instruqt random_id}"
export ZONE="${ZONE:-workshop.highvelocitynetworking.com}"
export AGENTS="ip-reputation,url-scanner,file-hash,cve-lookup,domain-age,asn-info,passive-dns,threat-feed"

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

export AGENTGATEWAY_IP="0.0.0.0"
"${SHARED}/coredns/render-corefile.sh" "${SHARED}/coredns/rendered"

"${SHARED}/dns-seed/bootstrap.sh"

cd "${HERE}"
docker compose up -d --build

echo
echo "── IETF2 sandbox up ───────────────────────────────────────────────"
echo "  Subdomain:  ${SANDBOX_SLUG}.${ZONE}"
echo "  Federation: 7 legit agents + 1 rogue (threat-feed)"
echo "  Visualizer: http://localhost:8080  (DNS-AID Explorer)"
echo
echo "Open the email from HR (it's on the dashboard) and start with"
echo "Challenge 1 in the Instruqt panel."
echo "───────────────────────────────────────────────────────────────────"
