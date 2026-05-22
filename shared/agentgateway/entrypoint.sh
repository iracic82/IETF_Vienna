#!/bin/sh
# Render the per-sandbox config from AGENTS env then exec agentgateway.
set -e

python3 /etc/agentgateway/render-config.py > /etc/agentgateway/config.yaml
echo "── rendered agentgateway config ─────────────────────────────────"
cat /etc/agentgateway/config.yaml
echo "─────────────────────────────────────────────────────────────────"

exec /usr/local/bin/agentgateway -f /etc/agentgateway/config.yaml
