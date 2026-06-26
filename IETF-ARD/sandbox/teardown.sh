#!/usr/bin/env bash
# IETF sandbox teardown. Best-effort.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARED="$(cd "${HERE}/../../shared" && pwd)"

export ZONE="${ZONE:-workshop.highvelocitynetworking.com}"
export AGENTS="ip-reputation"

cd "${HERE}"
docker compose down || true

"${SHARED}/dns-seed/teardown.sh" || true

echo "[teardown] IETF sandbox cleaned."
