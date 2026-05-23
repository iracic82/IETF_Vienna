#!/usr/bin/env bash
# Reproduce the translator's exact DNS query path from inside the container.
set -uo pipefail
source /opt/lab/lab.env 2>/dev/null || source /tmp/sandbox.env

CONTAINER=${1:-translator-debug}

cat > /tmp/_translator_resolve.py <<'PY'
"""Reproduce translator's discovery query exactly."""
import os, socket
import dns.exception, dns.rdatatype, dns.resolver

SLUG = os.environ["SANDBOX_SLUG"]
ZONE = os.environ["ZONE"]
DOMAIN = f"{SLUG}.{ZONE}"
NAME = "ip-reputation"
PROTOCOL = "mcp"
DNS_SERVER = "1.1.1.1"
DNS_PORT = 53

DNS_AID_FQDN = "_{name}._{protocol}._agents.{domain}"
fqdn = DNS_AID_FQDN.format(name=NAME, protocol=PROTOCOL, domain=DOMAIN)
print(f"FQDN constructed: {fqdn}")

# Mirror translator's _resolver()
try:
    ipaddress_str = socket.gethostbyname(DNS_SERVER)
except socket.gaierror as e:
    print(f"FAIL: gethostbyname({DNS_SERVER}) -> {e}")
    raise SystemExit(1)
print(f"DNS server resolved to: {ipaddress_str}")

r = dns.resolver.Resolver(configure=False)
r.nameservers = [ipaddress_str]
r.port = DNS_PORT
r.lifetime = 3.0

print(f"Resolver state: nameservers={r.nameservers} port={r.port} lifetime={r.lifetime}")

try:
    answer = r.resolve(fqdn, dns.rdatatype.SVCB)
    print(f"OK: {len(list(answer))} answer(s)")
    for rr in answer:
        print(f"  SVCB: {rr.to_text()}")
except dns.resolver.NXDOMAIN as e:
    print(f"NXDOMAIN: {e}")
except dns.resolver.NoAnswer as e:
    print(f"NoAnswer: {e}")
except dns.exception.DNSException as e:
    print(f"DNSException ({type(e).__name__}): {e}")
except Exception as e:
    print(f"Exception ({type(e).__name__}): {e}")
PY

docker cp /tmp/_translator_resolve.py ${CONTAINER}:/tmp/_translator_resolve.py
docker exec -e SANDBOX_SLUG=${SANDBOX_SLUG} -e ZONE=${ZONE} ${CONTAINER} python3 /tmp/_translator_resolve.py
