#!/usr/bin/env bash
# Render CoreDNS configs from templates. Called by sandbox bootstrap before
# `docker compose up`. Inputs come from env:
#   SANDBOX_SLUG       Instruqt-injected
#   ZONE               workshop.highvelocitynetworking.com
#   AGENTGATEWAY_IP    docker network IP of the agentgateway service
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-${HERE}/rendered}"
mkdir -p "${OUT}"

sed -e "s|{{SANDBOX_SLUG}}|${SANDBOX_SLUG}|g" \
    -e "s|{{ZONE}}|${ZONE}|g" \
    "${HERE}/Corefile.tmpl" > "${OUT}/Corefile"

sed -e "s|{{SANDBOX_SLUG}}|${SANDBOX_SLUG}|g" \
    -e "s|{{AGENTGATEWAY_IP}}|${AGENTGATEWAY_IP}|g" \
    "${HERE}/local.hosts.tmpl" > "${OUT}/local.hosts"

echo "[coredns] rendered → ${OUT}/Corefile + ${OUT}/local.hosts"
