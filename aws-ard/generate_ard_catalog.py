"""Generate an ARD-conformant ai-catalog.json from the existing
per-agent dns-aid v1.json cap docs in the ietf-vienna-cap-docs S3
bucket, then upload it to /.well-known/ai-catalog.json.

ARD spec references:
  - Catalog format:  https://agenticresourcediscovery.org/ai_catalog_spec/
  - Discovery spec:  https://agenticresourcediscovery.org/spec/
  - JSON Schema:     https://github.com/ards-project/ard-spec/blob/main/spec/schemas/ai-catalog.schema.json

Each existing dns-aid v1.json entry becomes one ARD catalog entry:

    dns-aid v1.json field        ARD entry field
    -----------------------      ----------------------
    agent                        identifier suffix (urn:air:lab.ccdesanity.com:agent:<agent>)
    capabilities[0]              tags[]
    tools[0].description         description
    mcp_server_card              url (resolves to the per-agent server card)
    policy_uri                   metadata.policy_uri
    trust.signer_hint            metadata.signer_hint
    tools                        metadata.tools (full list — useful for richer search)

Run: ./generate_ard_catalog.py [--upload]   # writes to /tmp by default;
                                            # --upload pushes to S3.
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
CATALOG_KEY = ".well-known/ai-catalog.json"
S3_BASE = f"https://{BUCKET}.s3.amazonaws.com"


def fetch_v1(agent: str) -> dict[str, Any] | None:
    url = f"{S3_BASE}/{agent}/v1.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  ⚠ skip {agent}: {exc}", file=sys.stderr)
        return None


def to_ard_entry(v1: dict[str, Any]) -> dict[str, Any]:
    """Translate one dns-aid v1.json into one ARD ai-catalog.json entry."""
    agent = v1["agent"]
    tools = v1.get("tools", [])
    capabilities = v1.get("capabilities", [])

    # ARD identifier format: urn:air:<publisher>:<namespace>:<agent-name>
    identifier = f"urn:air:{PUBLISHER}:agent:{agent}"

    # Description: prefer the first tool's description if richer than the
    # agent-level one. Fall back to a synthesised line if nothing useful
    # is present.
    description = (
        (tools[0].get("description") if tools else None)
        or f"{agent} capability published by {PUBLISHER}"
    )

    # Display name: humanise the agent slug (ip-reputation → "IP Reputation")
    display_name = " ".join(w.capitalize() for w in agent.replace("_", "-").split("-"))

    entry = {
        "identifier": identifier,
        "displayName": display_name,
        # The MCP server card is the canonical machine-readable handle for
        # how to talk to this agent — wire-protocol + endpoint + auth.
        "type": "application/mcp-server+json",
        "url": v1.get("mcp_server_card", f"{S3_BASE}/{agent}/mcp-server-card.json"),
        "description": description,
        "tags": capabilities,
        # ARD lets entries carry arbitrary metadata.*; we expose the bits
        # the lab's search Lambda + agent will key off.
        "metadata": {
            "cap_uri":  f"{S3_BASE}/{agent}/v1.json",
            "policy_uri": v1.get("policy_uri"),
            "policy_uri_strict": f"{S3_BASE}/{agent}/policy-strict.json",
            "version": v1.get("version"),
            "protocol": v1.get("protocol"),
            "transport": v1.get("transport"),
            "tools": [
                {"name": t["name"], "description": t.get("description", "")}
                for t in tools
            ],
            "signer_hint": (v1.get("trust") or {}).get("signer_hint"),
        },
        # Optional trust hints — pulls in the JWS signer reference from
        # the dns-aid cap doc. ARD §4.x supports trustManifest envelopes
        # but our lab's cap docs are unsigned (Route 53 TXT 255-char
        # limit blocks the JWS), so we surface "claimed signer" only.
        "trustManifest": {
            "claimedSigner": (v1.get("trust") or {}).get("signer_hint"),
            "jwksUri":       (v1.get("trust") or {}).get("jwks_uri"),
        },
    }
    return entry


def build_catalog(agents: list[str]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for agent in agents:
        v1 = fetch_v1(agent)
        if v1 is None:
            continue
        entries.append(to_ard_entry(v1))

    return {
        "specVersion": "1.0",
        "host": {
            "displayName": "CCDeSanity Threat-Intel Federation (IETF Lab)",
            "identifier": PUBLISHER,
        },
        "entries": entries,
    }


# The 8 agents the dns-aid lab publishes to S3. Hard-coded rather than
# enumerated dynamically because we want the catalog content to be
# review-stable and not silently change when someone uploads a stray
# file to the bucket.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--upload",
        action="store_true",
        help=f"After building, upload to s3://{BUCKET}/{CATALOG_KEY} via the "
             f"`aws --profile okta-sso` CLI. Without this flag the catalog "
             f"is only written to /tmp/ai-catalog.json for review.",
    )
    parser.add_argument(
        "--out",
        default="/tmp/ai-catalog.json",
        help="Where to write the generated catalog locally (default: /tmp/ai-catalog.json).",
    )
    args = parser.parse_args()

    catalog = build_catalog(LAB_AGENTS)
    with open(args.out, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"✓ wrote {args.out} ({len(catalog['entries'])} entries)")

    if args.upload:
        import subprocess
        subprocess.run(
            [
                "aws", "--profile", "okta-sso", "s3", "cp",
                args.out,
                f"s3://{BUCKET}/{CATALOG_KEY}",
                "--content-type", "application/json",
                "--cache-control", "public, max-age=300",
            ],
            check=True,
        )
        print(f"✓ uploaded to s3://{BUCKET}/{CATALOG_KEY}")
        print(f"  public URL: {S3_BASE}/{CATALOG_KEY}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
