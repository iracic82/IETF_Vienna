#!/usr/bin/env bash
# Test network reachability from inside the translator container.
# Run on the sandbox host. Reads SANDBOX_SLUG + ZONE from /opt/lab/lab.env.
set -uo pipefail

source /opt/lab/lab.env 2>/dev/null || source /tmp/sandbox.env

CONTAINER=${1:-translator-debug}
echo "Diagnosing network from container: ${CONTAINER}"
echo ""

cat > /tmp/_netcheck.py <<'PY'
import os, socket, ssl, urllib.request, json, struct

SLUG = os.environ["SANDBOX_SLUG"]
ZONE = os.environ["ZONE"]
FQDN = f"_ip-reputation._mcp._agents.{SLUG}.{ZONE}"

def hexdns(name):
    """Encode FQDN as DNS wire-format question for type=SVCB (64)."""
    out = b""
    for label in name.split("."):
        out += bytes([len(label)]) + label.encode()
    out += b"\x00"
    out += struct.pack(">HH", 64, 1)  # qtype=SVCB(64), qclass=IN
    header = b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    return header + out


print(f"FQDN under test: {FQDN}")
print()

# --- Test 1: UDP/53 to 1.1.1.1 -----------------------------------------
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    s.sendto(hexdns(FQDN), ("1.1.1.1", 53))
    data, _ = s.recvfrom(2048)
    print(f"[1] UDP/53 to 1.1.1.1   : OK ({len(data)} bytes)")
except Exception as e:
    print(f"[1] UDP/53 to 1.1.1.1   : FAIL — {type(e).__name__}: {e}")

# --- Test 2: TCP/53 to 1.1.1.1 -----------------------------------------
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(("1.1.1.1", 53))
    print(f"[2] TCP/53 to 1.1.1.1   : OK (connected)")
    s.close()
except Exception as e:
    print(f"[2] TCP/53 to 1.1.1.1   : FAIL — {type(e).__name__}: {e}")

# --- Test 3: DoH to 1.1.1.1 --------------------------------------------
try:
    url = f"https://1.1.1.1/dns-query?name={FQDN}&type=SVCB"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    r = urllib.request.urlopen(req, timeout=5)
    body = json.loads(r.read())
    print(f"[3] DoH HTTPS to 1.1.1.1 : OK status={body.get('Status')} ans_count={len(body.get('Answer') or [])}")
    for ans in (body.get("Answer") or [])[:3]:
        print(f"    answer: {ans}")
except Exception as e:
    print(f"[3] DoH HTTPS to 1.1.1.1 : FAIL — {type(e).__name__}: {e}")

# --- Test 4: UDP/53 to local coredns ------------------------------------
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    s.sendto(hexdns(FQDN), ("coredns", 53))
    data, _ = s.recvfrom(2048)
    print(f"[4] UDP/53 to coredns   : OK ({len(data)} bytes)")
except Exception as e:
    print(f"[4] UDP/53 to coredns   : FAIL — {type(e).__name__}: {e}")

# --- Test 5: dnspython resolve via 1.1.1.1 ------------------------------
try:
    import dns.resolver
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = ["1.1.1.1"]
    ans = r.resolve(FQDN, "SVCB")
    for rr in ans:
        print(f"[5] dnspython 1.1.1.1   : OK SVCB {rr.to_text()}")
except Exception as e:
    print(f"[5] dnspython 1.1.1.1   : FAIL — {type(e).__name__}: {e}")
PY

docker cp /tmp/_netcheck.py "${CONTAINER}":/tmp/_netcheck.py
docker exec -e SANDBOX_SLUG=${SANDBOX_SLUG} -e ZONE=${ZONE} "${CONTAINER}" python3 /tmp/_netcheck.py
