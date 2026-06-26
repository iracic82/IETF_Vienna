"""Generate spec-rich ARD ai-catalog.json from the existing per-agent
dns-aid v1.json cap docs in S3, then upload to:

  - Global reference:  s3://ietf-vienna-cap-docs/.well-known/ai-catalog.json
  - Per-student stub:  s3://ietf-vienna-cap-docs/students/<slug>/.well-known/ai-catalog.json
                       (empty entries[]; student's C2 publish step appends)

ARD spec references (everything below cross-references one of these):
  - https://agenticresourcediscovery.org/spec/         (full)
  - https://agenticresourcediscovery.org/ai_catalog_spec/  (envelope)
  - https://github.com/ards-project/ard-spec/blob/main/spec/schemas/ai-catalog.schema.json
  - https://github.com/ards-project/ard-spec/blob/main/spec/schemas/ard.cddl

Field coverage (all fields the spec defines that "make sense to be
there" for a federation catalog like this one):

  envelope:
    specVersion           §AI Catalog spec — core envelope
    host                  §AI Catalog spec — host with displayName + identifier
    entries[]             §AI Catalog spec — array of CatalogEntry
    collections[]         §AI Catalog spec — sub-catalog links (we use this
                          to point at per-student federation members)

  entry:
    identifier            §4.2.1 — urn:air:<publisher>:<namespace>:<agent>
    displayName           §4.x baseline
    type                  §AI Catalog — IANA-style media type
    url                   §AI Catalog — fetchable resource URL
    description           §AI Catalog — Schema.org-tagged when relevant
    tags                  §7.1 — filter dimension
    metadata.*            §AI Catalog — extension namespace; we expose
                          cap_uri, policy_uri, policy_uri_strict, version,
                          protocol, transport, tools (richer search basis)
    schemaOrg             §4.5 — structured vocabulary attached to the
                          description (provider, areaServed, audience,
                          isAccessibleForFree, etc.)
    trustManifest         §5.1 — identity + identityType + attestations
                          + provenance + (optional) signature

Run:
    ./generate_ard_catalog.py                    # global only, /tmp preview
    ./generate_ard_catalog.py --upload           # global → S3
    ./generate_ard_catalog.py --slug d754cf9c    # stub student catalog
    ./generate_ard_catalog.py --slug d754cf9c --upload
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

BUCKET = "ietf-vienna-cap-docs"
PUBLISHER = "lab.ccdesanity.com"
GLOBAL_CATALOG_KEY = ".well-known/ai-catalog.json"
PER_STUDENT_PREFIX = "students"
S3_BASE = f"https://{BUCKET}.s3.amazonaws.com"


# Display + Schema.org metadata enrichment per agent. These are derived
# from each agent's cap doc by display name + capability, then layered
# with realistic enterprise metadata so the catalog reads like a real
# federation manifest, not a 4-field stub.
#
# Keys = agent slug; values = enrichment overrides merged into the
# auto-derived entry. If an agent isn't in this map, sensible defaults
# from the cap doc are used.
AGENT_ENRICHMENT: dict[str, dict[str, Any]] = {
    "ip-reputation": {
        "displayName": "IP Reputation",
        "description": (
            "Real-time IPv4 reputation verdict (malicious / suspicious / clean) "
            "with confidence score and citation sources (tor-exit-list, abuse.ch, "
            "Spamhaus, etc.). Threat-intel federation member."
        ),
        "tags": ["ip-reputation", "threat-intel", "ipv4", "reputation"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "ThreatIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
            "areaServed": "global",
            "audience": {"@type": "Audience", "audienceType": "security_analyst"},
            "isAccessibleForFree": True,
        },
    },
    "url-scanner": {
        "displayName": "URL Scanner",
        "description": (
            "Static and dynamic URL analysis: phishing, malware-hosting, "
            "and known-bad redirects. Returns category + risk score."
        ),
        "tags": ["url-scanning", "phishing", "malware", "threat-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "URLAnalysis",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
        },
    },
    "asn-info": {
        "displayName": "ASN Information",
        "description": (
            "Autonomous System lookup: ASN number, owning organisation, "
            "country, and ISP for any IPv4 or IPv6 address."
        ),
        "tags": ["asn", "ipam", "geo-ip", "network-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "NetworkIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity NetOps"},
        },
    },
    "cve-lookup": {
        "displayName": "CVE Lookup",
        "description": (
            "Common Vulnerabilities and Exposures lookup by CVE ID. Returns "
            "CVSS score, affected products, exploitation status, and references."
        ),
        "tags": ["cve", "vulnerability", "cvss", "security-advisory"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "VulnerabilityIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity ProdSec"},
        },
    },
    "domain-age": {
        "displayName": "Domain Age",
        "description": (
            "WHOIS-derived domain registration age. Highly correlated with "
            "phishing campaigns (young domains over-represented in attacks)."
        ),
        "tags": ["domain-age", "whois", "phishing-indicator", "threat-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "DomainIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
        },
    },
    "file-hash": {
        "displayName": "File Hash Lookup",
        "description": (
            "SHA-256 / MD5 / SHA-1 hash lookup against multi-source malware "
            "intelligence feeds. Returns first-seen date and matching engines."
        ),
        "tags": ["file-hash", "malware", "sha256", "threat-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "FileIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
        },
    },
    "passive-dns": {
        "displayName": "Passive DNS",
        "description": (
            "Historical DNS resolution records. Query by domain to see all "
            "observed IPs over time, or by IP to see all domains that have "
            "resolved to it. Cornerstone of infrastructure pivoting."
        ),
        "tags": ["passive-dns", "pdns", "infrastructure-intel", "threat-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "DNSHistoricalIntelligence",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
        },
    },
    "threat-feed": {
        "displayName": "Threat Feed",
        "description": (
            "Bulk indicators-of-compromise (IoC) feed with categorisation, "
            "severity, and first-seen timestamps. Pull or stream interface."
        ),
        "tags": ["threat-feed", "ioc", "stix", "threat-intel"],
        "schemaOrg": {
            "@type": "Service",
            "serviceType": "ThreatFeedAggregation",
            "provider": {"@type": "Organization", "name": "CCDeSanity SOC"},
        },
    },
}


def fetch_v1(agent: str) -> dict[str, Any] | None:
    url = f"{S3_BASE}/{agent}/v1.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  ⚠ skip {agent}: {exc}", file=sys.stderr)
        return None


def _humanise(agent: str) -> str:
    return " ".join(w.capitalize() for w in agent.replace("_", "-").split("-"))


def _trust_manifest(agent: str, v1: dict[str, Any], publisher: str) -> dict[str, Any]:
    """Build a §5.1 Trust Manifest. SPIFFE-style identity that aligns
    with the entry identifier's domain (the spec's authority-binding
    requirement). Attestations + provenance are populated as realistic
    enterprise placeholders so students see the shape."""
    trust = v1.get("trust") or {}
    return {
        "identity": f"spiffe://{publisher}/agents/{agent}",
        "identityType": "spiffe",
        "attestations": [
            {
                "type": "SOC2-Type2",
                "issuer": f"audit.{publisher}",
                "issuedAt": "2026-04-01T00:00:00Z",
                "expiresAt": "2027-04-01T00:00:00Z",
            },
            {
                "type": "iso27001",
                "issuer": f"audit.{publisher}",
                "issuedAt": "2026-01-15T00:00:00Z",
                "expiresAt": "2029-01-15T00:00:00Z",
            },
        ],
        "provenance": [
            {
                "type": "build-attestation",
                "buildSystem": "GitHub Actions",
                "buildId": f"ghc-{agent}-2026-06",
                "sourceRepo": "https://github.com/iracic82/IETF_Vienna",
            }
        ],
        # The dns-aid cap doc's signer_hint becomes a claimed-signer ref
        # alongside the JWKS pointer. Real federations would also fill
        # `signature` with a detached JWS over this trustManifest.
        "claimedSigner": trust.get("signer_hint"),
        "jwksUri": trust.get("jwks_uri"),
    }


def to_ard_entry(v1: dict[str, Any], publisher: str = PUBLISHER) -> dict[str, Any]:
    """Translate one dns-aid v1.json into one spec-rich ARD CatalogEntry."""
    agent = v1["agent"]
    tools = v1.get("tools", [])
    capabilities = v1.get("capabilities", [])
    enrich = AGENT_ENRICHMENT.get(agent, {})

    identifier = f"urn:air:{publisher}:agent:{agent}"
    display_name = enrich.get("displayName") or _humanise(agent)
    description = enrich.get("description") or (
        (tools[0].get("description") if tools else None)
        or f"{agent} capability published by {publisher}"
    )
    tags = enrich.get("tags") or capabilities

    entry: dict[str, Any] = {
        "identifier": identifier,
        "displayName": display_name,
        "type": "application/mcp-server+json",
        "url": v1.get("mcp_server_card", f"{S3_BASE}/{agent}/mcp-server-card.json"),
        "description": description,
        "tags": tags,
        # §AI Catalog metadata.* extension namespace — anything the lab's
        # search Lambda or the agent will key off lives here. dns-aid 0.26
        # will read these to translate into its DiscoveredAgent shape.
        "metadata": {
            "cap_uri":            f"{S3_BASE}/{agent}/v1.json",
            "policy_uri":          v1.get("policy_uri"),
            "policy_uri_strict": f"{S3_BASE}/{agent}/policy-strict.json",
            "version":             v1.get("version"),
            "protocol":            v1.get("protocol"),
            "transport":           v1.get("transport"),
            "tools": [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "inputSchema": t.get("inputSchema"),
                }
                for t in tools
            ],
        },
        # §5.1 — required trust envelope. The identity domain (PUBLISHER)
        # MUST match the publisher segment of the URN identifier above.
        "trustManifest": _trust_manifest(agent, v1, publisher),
    }

    # §4.5 — Schema.org vocabulary used as filter dimensions
    if "schemaOrg" in enrich:
        entry["schemaOrg"] = enrich["schemaOrg"]

    return entry


# The 8 agents the dns-aid lab publishes to S3.
LAB_AGENTS = [
    "asn-info",
    "cve-lookup",
    "domain-age",
    "file-hash",
    "ip-reputation",
    "passive-dns",
    "threat-feed",
    "url-scanner",
]


def build_global_catalog() -> dict[str, Any]:
    entries = []
    for agent in LAB_AGENTS:
        v1 = fetch_v1(agent)
        if v1 is None:
            continue
        entries.append(to_ard_entry(v1))

    return {
        "specVersion": "1.0",
        "host": {
            "displayName": "CCDeSanity Threat-Intel Federation (IETF Vienna ARD lab)",
            "identifier": PUBLISHER,
            # Optional enrichment — gives the host envelope real shape.
            "contact": "mailto:soc@lab.ccdesanity.com",
            "termsOfService": f"https://{PUBLISHER}/terms",
            "publishedAt": "2026-06-26T00:00:00Z",
        },
        "entries": entries,
        # §AI Catalog `collections` — sub-catalogs or related feeds.
        # The lab uses this to advertise per-student catalogs as
        # federation members. dns-aid clients (or any ARD-aware
        # discovery agent) can crawl `collections` to enumerate the
        # full federation.
        "collections": [
            {
                "identifier": f"urn:air:{PUBLISHER}:collection:per-student",
                "displayName": "Per-student sandbox catalogs",
                "description": (
                    "Each lab participant publishes their own catalog under "
                    f"{S3_BASE}/{PER_STUDENT_PREFIX}/<slug>/.well-known/ai-catalog.json. "
                    "Use the registry's /search?slug=<slug> endpoint to query a specific student's."
                ),
                "type": "application/ai-registry",
                "url": f"{S3_BASE}/{PER_STUDENT_PREFIX}/",
            }
        ],
    }


def build_student_stub(slug: str) -> dict[str, Any]:
    """Empty per-student catalog the C2 publish step will append to."""
    return {
        "specVersion": "1.0",
        "host": {
            "displayName": f"Sandbox {slug} — student federation",
            "identifier": f"{slug}.{PUBLISHER}",
            "contact": f"mailto:{slug}@students.{PUBLISHER}",
            "publishedAt": "2026-06-26T00:00:00Z",
        },
        "entries": [],
    }


def _upload(local_path: str, key: str) -> None:
    import subprocess
    subprocess.run(
        [
            "aws", "--profile", "okta-sso", "s3", "cp",
            local_path,
            f"s3://{BUCKET}/{key}",
            "--content-type", "application/json",
            "--cache-control", "public, max-age=60",
        ],
        check=True,
    )
    print(f"✓ uploaded → s3://{BUCKET}/{key}")
    print(f"  public URL: {S3_BASE}/{key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slug",
        help=("Build an empty per-student catalog under "
              "students/<slug>/.well-known/ai-catalog.json instead of "
              "the global one. The student's C2 publish step appends entries."),
    )
    parser.add_argument("--upload", action="store_true", help="Push to S3.")
    parser.add_argument("--out", default=None,
                        help="Local output path (default: /tmp/ai-catalog{-<slug>}.json).")
    args = parser.parse_args()

    if args.slug:
        catalog = build_student_stub(args.slug)
        out_path = args.out or f"/tmp/ai-catalog-{args.slug}.json"
        s3_key = f"{PER_STUDENT_PREFIX}/{args.slug}/{GLOBAL_CATALOG_KEY}"
        label = f"student stub for slug={args.slug}"
    else:
        catalog = build_global_catalog()
        out_path = args.out or "/tmp/ai-catalog.json"
        s3_key = GLOBAL_CATALOG_KEY
        label = "global reference catalog"

    with open(out_path, "w") as f:
        json.dump(catalog, f, indent=2)
    n = len(catalog.get("entries", []))
    print(f"✓ wrote {out_path} — {label}, {n} entries")

    if args.upload:
        _upload(out_path, s3_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
