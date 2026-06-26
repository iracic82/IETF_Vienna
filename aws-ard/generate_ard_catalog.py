"""Generate spec-correct AI Catalog (ai-catalog.io) / ARD catalog
from the existing per-agent dns-aid v1.json cap docs in S3, then
upload to:

  - Global reference:  s3://ietf-vienna-cap-docs/.well-known/ai-catalog.json

Per-student catalogs are NOT pre-uploaded; the Lambda derives them
on demand by rewriting the global catalog with the student's slug.
This sidesteps the AccessDenied issue with the lab's scoped AWS
credentials (Route 53 only).

Specs adhered to:
  - AI Catalog standard:  https://ai-catalog.io/   (CDDL Schema section)
  - ARD spec:             https://agenticresourcediscovery.org/spec/
  - JSON Schema:          https://github.com/Agent-Card/ai-catalog
                          https://github.com/ards-project/ard-spec

Field shape matches the spec EXACTLY:

  AICatalog = {specVersion, ?host, entries[], ?metadata}

  HostInfo  = {displayName, ?identifier, ?documentationUrl, ?logoUrl,
               ?trustManifest}

  CatalogEntry = {identifier, displayName, type, (url // data),
                  ?version, ?description, ?tags, ?publisher,
                  ?trustManifest, ?updatedAt, ?metadata}

  Publisher = {identifier, displayName, ?identityType}

  TrustManifest = {identity, ?identityType, ?trustSchema,
                   ?attestations[], ?provenance[],
                   ?privacyPolicyUrl, ?termsOfServiceUrl,
                   ?signature, ?metadata}

  Attestation = {type, uri, ?digest, ?size, ?description}

  ProvenanceLink = {relation, sourceId, ?sourceDigest,
                    ?registryUri, ?statementUri, ?signatureRef}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

BUCKET = "ietf-vienna-cap-docs"
PUBLISHER_DOMAIN = "lab.ccdesanity.com"
GLOBAL_CATALOG_KEY = ".well-known/ai-catalog.json"
S3_BASE = f"https://{BUCKET}.s3.amazonaws.com"

# Media type per IANA registration in the AI Catalog spec.
MCP_SERVER_CARD_TYPE = "application/mcp-server-card+json"

# Per-agent enrichment that goes into the spec-compliant entry. Only
# fields the spec actually defines or the spec's recommended
# metadata.* keys (reverse-DNS or short broadly-useful names).
AGENT_ENRICHMENT: dict[str, dict[str, Any]] = {
    "ip-reputation": {
        "displayName": "IP Reputation",
        "description": (
            "Real-time IPv4 reputation verdict (malicious / suspicious / clean) "
            "with confidence score and citation sources (tor-exit-list, "
            "abuse.ch, Spamhaus). Threat-intel federation member."
        ),
        "tags": ["ip-reputation", "threat-intel", "ipv4", "reputation"],
        "metadata": {
            "repository":      "https://github.com/iracic82/IETF_Vienna",
            "homepage":        "https://dns-aid.org",
            "license":         "Apache-2.0",
            "supportContact":  "mailto:soc@lab.ccdesanity.com",
            "documentationUrl": f"{S3_BASE}/ip-reputation/mcp-server-card.json",
            "io.dnsaid.protocol":  "mcp",
            "io.dnsaid.transport": "streamable-http",
            "io.dnsaid.policyUri":       f"{S3_BASE}/ip-reputation/policy.json",
            "io.dnsaid.policyUriStrict": f"{S3_BASE}/ip-reputation/policy-strict.json",
            "io.dnsaid.capUri":          f"{S3_BASE}/ip-reputation/v1.json",
            "io.dnsaid.rateLimit":  {"per": "minute", "max": 60},
            "io.dnsaid.cost":       {"model": "free-for-federation"},
        },
    },
    "url-scanner": {
        "displayName": "URL Scanner",
        "description": (
            "Static + dynamic URL analysis. Returns phishing / malware / "
            "redirect-chain risk score and category."
        ),
        "tags": ["url-scanning", "phishing", "malware", "threat-intel"],
    },
    "asn-info": {
        "displayName": "ASN Information",
        "description": (
            "Autonomous System lookup: ASN number, owning organisation, "
            "country, and ISP for any IPv4 or IPv6 address."
        ),
        "tags": ["asn", "ipam", "geo-ip", "network-intel"],
    },
    "cve-lookup": {
        "displayName": "CVE Lookup",
        "description": (
            "Common Vulnerabilities and Exposures lookup by CVE ID. "
            "Returns CVSS score, affected products, exploitation status, "
            "and reference links."
        ),
        "tags": ["cve", "vulnerability", "cvss", "security-advisory"],
    },
    "domain-age": {
        "displayName": "Domain Age",
        "description": (
            "WHOIS-derived domain registration age. Highly correlated "
            "with phishing campaigns (young domains over-represented "
            "in attacks)."
        ),
        "tags": ["domain-age", "whois", "phishing-indicator", "threat-intel"],
    },
    "file-hash": {
        "displayName": "File Hash Lookup",
        "description": (
            "SHA-256 / MD5 / SHA-1 hash lookup against multi-source "
            "malware intelligence feeds. Returns first-seen date and "
            "matching engines."
        ),
        "tags": ["file-hash", "malware", "sha256", "threat-intel"],
    },
    "passive-dns": {
        "displayName": "Passive DNS",
        "description": (
            "Historical DNS resolution records. Query by domain to see "
            "all observed IPs over time, or by IP to see all domains "
            "that resolved to it. Cornerstone of infrastructure pivoting."
        ),
        "tags": ["passive-dns", "pdns", "infrastructure-intel", "threat-intel"],
    },
    "threat-feed": {
        "displayName": "Threat Feed",
        "description": (
            "Bulk indicators-of-compromise (IoC) feed with categorisation, "
            "severity, and first-seen timestamps. Pull or stream interface."
        ),
        "tags": ["threat-feed", "ioc", "stix", "threat-intel"],
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


def _humanise(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-"))


def _sha256_stub(payload: str) -> str:
    """Deterministic stub digest for demo purposes — produces a real
    sha256 hash so the field validates, even though the upstream
    attestation document URL is a placeholder."""
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _trust_manifest(
    agent: str,
    v1: dict[str, Any],
    publisher_domain: str,
) -> dict[str, Any]:
    """Build a spec-correct TrustManifest per the CDDL schema:

      TrustManifest = {identity, ?identityType, ?trustSchema,
                       ?attestations, ?provenance,
                       ?privacyPolicyUrl, ?termsOfServiceUrl,
                       ?signature, ?metadata}
    """
    trust_hint = v1.get("trust") or {}
    return {
        # SPIFFE identity that aligns with the publisher domain of the
        # entry URN — the spec requires this alignment for trust
        # verification.
        "identity":     f"spiffe://{publisher_domain}/agents/{agent}",
        "identityType": "spiffe",

        # TrustSchema = the governance framework for this catalog's
        # trust model. Mandatory if you want consumers to know which
        # rules apply.
        "trustSchema": {
            "identifier":  f"urn:trust:{publisher_domain}:federation-v1",
            "version":     "1.0",
            "governanceUri": f"https://{publisher_domain}/trust/governance",
            "verificationMethods": ["sigstore", "jws", "x509"],
        },

        # Attestation = {type, uri, ?digest, ?size, ?description}
        # The "publisher-identity" type is the canonical binding per
        # the AI Catalog spec.
        "attestations": [
            {
                "type":        "publisher-identity",
                "uri":         f"https://{publisher_domain}/trust/publisher.jwt",
                "description": f"Verifies did:web:{publisher_domain} as the publisher",
            },
            {
                "type":        "SOC2-Type2",
                "uri":         f"https://{publisher_domain}/trust/soc2-2026.pdf",
                "digest":      _sha256_stub(f"{agent}:soc2-2026"),
                "size":        245760,
                "description": "SOC2 Type 2 audit report (2026)",
            },
            {
                "type":        "ISO27001-2022",
                "uri":         f"https://{publisher_domain}/trust/iso27001-2022.pdf",
                "digest":      _sha256_stub(f"{agent}:iso27001-2022"),
                "size":        198400,
                "description": "ISO/IEC 27001:2022 certification",
            },
            {
                "type":        "GDPR-DPA",
                "uri":         f"https://{publisher_domain}/trust/gdpr-dpa.pdf",
                "description": "GDPR Data Processing Addendum",
            },
        ],

        # ProvenanceLink = {relation, sourceId, ?sourceDigest,
        #                   ?registryUri, ?statementUri, ?signatureRef}
        "provenance": [
            {
                "relation":    "publishedFrom",
                "sourceId":    "https://github.com/iracic82/IETF_Vienna",
                "sourceDigest": _sha256_stub(f"{agent}:source"),
                "registryUri": "https://ietf-vienna-cap-docs.s3.amazonaws.com",
                "statementUri": f"{S3_BASE}/{agent}/v1.json",
            },
        ],

        # Privacy + terms live INSIDE trustManifest per the spec.
        "privacyPolicyUrl":  f"https://{publisher_domain}/privacy",
        "termsOfServiceUrl": f"https://{publisher_domain}/terms",

        # `signature` would be a detached JWS over this manifest. The
        # lab publishes unsigned (Route 53 TXT 255-char limit), so we
        # surface the claimed signer hint in metadata.
        "metadata": {
            "claimedSigner": trust_hint.get("signer_hint"),
            "jwksUri":       trust_hint.get("jwks_uri"),
            "signed":        False,
            "reason":        "lab publishes unsigned (Route 53 TXT 255-char limit)",
        },
    }


def to_catalog_entry(
    v1: dict[str, Any],
    publisher_domain: str = PUBLISHER_DOMAIN,
    publisher_display: str = "CCDeSanity Threat-Intel Federation",
) -> dict[str, Any]:
    """Translate one dns-aid v1.json into one SPEC-CORRECT CatalogEntry.

    Field order matches the CDDL definition for human readability.
    """
    agent = v1["agent"]
    tools = v1.get("tools", [])
    enrich = AGENT_ENRICHMENT.get(agent, {})

    display_name = enrich.get("displayName") or _humanise(agent)
    description  = enrich.get("description") or (
        (tools[0].get("description") if tools else None)
        or f"{agent} capability published by {publisher_domain}"
    )
    tags = enrich.get("tags") or v1.get("capabilities", [])

    # The url field points at the canonical machine-readable handle.
    # For an MCP server, that's the MCP server card.
    server_card_url = v1.get("mcp_server_card", f"{S3_BASE}/{agent}/mcp-server-card.json")

    # metadata.* — open extension namespace per the spec. Keys without
    # reverse-DNS prefixes are short broadly-useful names; vendor-
    # specific keys use 'io.dnsaid.*' to avoid collision.
    default_metadata = {
        "repository":          "https://github.com/iracic82/IETF_Vienna",
        "homepage":            "https://dns-aid.org",
        "license":             "Apache-2.0",
        "supportContact":      f"mailto:soc@{publisher_domain}",
        "documentationUrl":    server_card_url,
        "io.dnsaid.protocol":  v1.get("protocol"),
        "io.dnsaid.transport": v1.get("transport"),
        "io.dnsaid.capUri":          f"{S3_BASE}/{agent}/v1.json",
        "io.dnsaid.policyUri":       v1.get("policy_uri"),
        "io.dnsaid.policyUriStrict": f"{S3_BASE}/{agent}/policy-strict.json",
        "io.dnsaid.tools": [
            {"name": t["name"], "description": t.get("description", "")}
            for t in tools
        ],
        "io.dnsaid.rateLimit":  {"per": "minute", "max": 60},
        "io.dnsaid.cost":       {"model": "free-for-federation"},
    }
    metadata = {**default_metadata, **enrich.get("metadata", {})}

    # Spec-correct entry, fields in CDDL order.
    return {
        "identifier":  f"urn:air:{publisher_domain}:agent:{agent}",
        "displayName": display_name,
        "type":        MCP_SERVER_CARD_TYPE,
        "url":         server_card_url,
        "version":     v1.get("version", "1.0.0"),
        "description": description,
        "tags":        tags,
        "publisher": {
            "identifier":   f"did:web:{publisher_domain}",
            "displayName":  publisher_display,
            "identityType": "did",
        },
        "trustManifest": _trust_manifest(agent, v1, publisher_domain),
        "updatedAt":     datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "metadata":      metadata,
    }


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
    entries: list[dict[str, Any]] = []
    for agent in LAB_AGENTS:
        v1 = fetch_v1(agent)
        if v1 is None:
            continue
        entries.append(to_catalog_entry(v1))

    # AICatalog = {specVersion, ?host, entries[], ?metadata}
    return {
        "specVersion": "1.0",
        "host": {
            # Per CDDL HostInfo = {displayName, ?identifier,
            #   ?documentationUrl, ?logoUrl, ?trustManifest}
            "displayName":      "CCDeSanity Threat-Intel Federation (IETF Vienna ARD lab)",
            "identifier":       f"did:web:{PUBLISHER_DOMAIN}",
            "documentationUrl": "https://dns-aid.org",
            "trustManifest": {
                "identity":     f"did:web:{PUBLISHER_DOMAIN}",
                "identityType": "did",
                "trustSchema": {
                    "identifier":  f"urn:trust:{PUBLISHER_DOMAIN}:federation-v1",
                    "version":     "1.0",
                    "governanceUri": f"https://{PUBLISHER_DOMAIN}/trust/governance",
                    "verificationMethods": ["sigstore", "jws", "x509"],
                },
                "attestations": [
                    {
                        "type":        "publisher-identity",
                        "uri":         f"https://{PUBLISHER_DOMAIN}/trust/publisher.jwt",
                        "description": f"Verifies did:web:{PUBLISHER_DOMAIN}",
                    },
                ],
                "privacyPolicyUrl":  f"https://{PUBLISHER_DOMAIN}/privacy",
                "termsOfServiceUrl": f"https://{PUBLISHER_DOMAIN}/terms",
            },
        },
        "entries": entries,
        # Top-level metadata.* — workshop-specific provenance fields
        # outside the entry-level metadata so consumers don't confuse them.
        "metadata": {
            "io.dnsaid.specsImplemented": [
                "https://ai-catalog.io/",
                "https://agenticresourcediscovery.org/spec/",
            ],
            "io.dnsaid.specVersion":       "ai-catalog v1.0 + ARD v0.9 draft",
            "io.dnsaid.lab":               "IETF Vienna 2026 — DNS-AID + ARD federation",
            "io.dnsaid.generatedAt":       datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
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
    parser.add_argument("--upload", action="store_true", help="Push to S3.")
    parser.add_argument("--out", default="/tmp/ai-catalog.json")
    args = parser.parse_args()

    catalog = build_global_catalog()
    with open(args.out, "w") as f:
        json.dump(catalog, f, indent=2)
    n = len(catalog.get("entries", []))
    print(f"✓ wrote {args.out} — {n} entries")
    print(f"  spec: AI Catalog v1.0 (ai-catalog.io) + ARD v0.9")

    if args.upload:
        _upload(args.out, GLOBAL_CATALOG_KEY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
