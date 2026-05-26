#!/usr/bin/env bash
# Wraps dns-aid publish with the two workarounds students need:
#
#   1. Wait for CoreDNS negative-cache expiry (set to 5s in Corefile)
#      and the translator's next poll cycle to push the new SVCB into
#      agentgateway's xDS state.
#
#   2. Force agentgateway to re-subscribe to xDS so the data plane
#      picks up the new route. Without this, agentgateway shows the
#      route in /config_dump (desired state) but returns 404 on the
#      data plane — a known delta-xDS application bug in agentgateway
#      v1.3.0-alpha.1 (filed upstream).
#
# Pass all dns-aid publish args through:
#
#   scripts/publish-agent.sh \
#       --name ip-reputation --domain "${SANDBOX_SLUG}.${ZONE}" \
#       --protocol mcp --endpoint fastmcp-ip-reputation --port 3000 \
#       --transport streamable-http --capability ip-reputation \
#       --cap-uri "${CAP_BASE_URL}/ip-reputation/v1.json" \
#       --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json" \
#       --ttl 30
set -euo pipefail

source /opt/lab/lab.env 2>/dev/null || source /tmp/sandbox.env

echo "[publish] dns-aid publish $*"
dns-aid publish "$@"

echo ""
echo "[publish] waiting 12s for translator to poll DNS + push xDS to gateway"
sleep 12

echo "[publish] restarting agentgateway to force xDS re-subscription"
sudo docker restart agentgateway >/dev/null
sleep 5

echo "[publish] gateway state:"
curl -s http://localhost:15000/config_dump \
  | python3 -c "import json,sys; d=json.load(sys.stdin); ls=list(d.get('binds',[{}])[0].get('listeners',{}).values()); rs=list((ls[0] if ls else {}).get('routes',{}).keys()) if ls else []; print(f'  routes:   {rs}'); print(f'  backends: {len(d.get(\"backends\",[]))}')"

echo ""
echo "[publish] done. Verify with:"
echo "  curl -sw '%{http_code}\\n' -o /dev/null -X POST http://localhost:3000/<agent>/mcp \\"
echo "      -H 'content-type: application/json' \\"
echo "      -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}'"
