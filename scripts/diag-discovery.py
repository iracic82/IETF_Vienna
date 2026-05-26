"""
Diagnose translator discovery: run the exact DNS queries it would run.

Usage (inside the translator container):
    python3 /tmp/diag-discovery.py <slug> <zone> <agent>

Example:
    python3 /tmp/diag-discovery.py d754cf9c lab.ccdesanity.com ip-reputation
"""
import socket
import sys

import dns.exception
import dns.rdatatype
import dns.resolver


def query(resolver: dns.resolver.Resolver, name: str, rtype: str) -> None:
    print(f"\n--- {rtype} {name}")
    try:
        ans = resolver.resolve(name, rtype)
        print(f"OK: {len(list(ans))} answer(s)")
        for rr in ans:
            print(f"  {rtype}: {rr.to_text()}")
    except dns.resolver.NXDOMAIN as e:
        print(f"NXDOMAIN: {e}")
    except dns.resolver.NoAnswer as e:
        print(f"NoAnswer: {e}")
    except dns.exception.DNSException as e:
        print(f"DNSException ({type(e).__name__}): {e}")
    except Exception as e:
        print(f"Exception ({type(e).__name__}): {e}")


def main() -> None:
    slug, zone, agent = sys.argv[1], sys.argv[2], sys.argv[3]
    domain = f"{slug}.{zone}"

    dns_server = "coredns"
    try:
        dns_ip = socket.gethostbyname(dns_server)
    except socket.gaierror as e:
        print(f"FAIL: cannot resolve coredns container name: {e}")
        sys.exit(1)

    print(f"DNS server: {dns_server} -> {dns_ip}:53")
    print(f"Domain    : {domain}")
    print(f"Agent     : {agent}")

    r = dns.resolver.Resolver(configure=False)
    r.nameservers = [dns_ip]
    r.port = 53
    r.lifetime = 3.0

    query(r, f"_{agent}._mcp._agents.{domain}", "SVCB")
    query(r, f"_{agent}._mcp._agents.{domain}", "TXT")
    query(r, f"_index._agents.{domain}", "TXT")
    query(r, f"{domain}", "SOA")


if __name__ == "__main__":
    main()
