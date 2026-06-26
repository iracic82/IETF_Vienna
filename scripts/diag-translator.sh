#!/usr/bin/env bash
# Diagnose why the translator isn't picking up published DNS-AID records.
# Run on the sandbox host. Reads SANDBOX_SLUG + ZONE from /opt/lab/lab.env.
set -uo pipefail

source /opt/lab/lab.env 2>/dev/null || source /tmp/sandbox.env

echo "── 1. SVCB from inside translator container (using dig) ──"
docker exec translator sh -c "command -v dig >/dev/null 2>&1 && dig +noall +answer SVCB ip-reputation.${SANDBOX_SLUG}.${ZONE} @1.1.1.1 || echo 'dig not in container; trying python'"

echo ""
echo "── 2. SVCB from inside translator container (using python dnspython) ──"
docker exec translator python3 - <<PY
import dns.resolver
r = dns.resolver.Resolver(configure=False)
r.nameservers = ["1.1.1.1"]
fqdn = "ip-reputation.${SANDBOX_SLUG}.${ZONE}"
print("Querying:", fqdn)
try:
    ans = r.resolve(fqdn, "SVCB")
    for rr in ans:
        print("OK SVCB:", rr.to_text())
except Exception as e:
    print("ERROR:", type(e).__name__, str(e))
PY

echo ""
echo "── 3. Restart translator with DEBUG logging ──"
NET=$(docker network ls --format '{{.Name}}' | grep -E "lab|sandbox" | head -1)
echo "Using network: ${NET}"

docker rm -f translator-debug 2>/dev/null
docker compose -f /opt/lab/IETF_Vienna/IETF/sandbox/docker-compose.yml stop translator 2>/dev/null

docker run -d --name translator-debug --network "${NET}" \
    ghcr.io/iracic82/dns-aid-translator:0.3.0 \
    --mode=xds \
    --domain="${SANDBOX_SLUG}.${ZONE}" \
    --protocol=mcp \
    --agents ip-reputation \
    --dns-server=1.1.1.1 --dns-port=53 \
    --xds-listen=0.0.0.0:18000 \
    --interval=5 \
    --log-level=DEBUG >/dev/null

echo "Waiting 12s for the translator to do 2 poll cycles..."
sleep 12

echo ""
echo "── 4. Last 80 lines of DEBUG translator log ──"
docker logs translator-debug --tail 80 2>&1
