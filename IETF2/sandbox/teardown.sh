#!/usr/bin/env bash
# IETF2 sandbox teardown. Best-effort.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

export ZONE="${ZONE:-workshop.highvelocitynetworking.com}"
export AGENTS="ip-reputation,url-scanner,file-hash,cve-lookup,domain-age,asn-info,passive-dns,threat-feed"

cd "${HERE}"
docker compose down || true
"${SHARED}/dns-seed/teardown.sh" || true

echo "[teardown] IETF2 sandbox cleaned."
