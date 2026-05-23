---
slug: publish-your-agent
id: 2kfzxpqcouix
type: challenge
title: 2. Publish your federation capability (signed + externally hosted cap)
teaser: Sign and publish the ip-reputation DNS-AID record. Cap doc + MCP server card
  live in a public S3 bucket.
notes:
- type: text
  contents: |-
    You publish — by hand — the DNS-AID record that lets other
    federation members discover your capability. The record is JWS-signed
    with your sandbox's EC P-256 key, and it points at a cap doc + MCP
    Server Card + policy doc hosted publicly on S3 — the same docs every
    other learner sees. dns-aid talks to Route 53 directly using the
    Instruqt-injected secrets.
tabs:
- id: mxmrbnn0bk7x
  title: Terminal
  type: terminal
  hostname: host
- id: tlrymxfxefkc
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: qtwx3muuwfqo
  title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 900
enhanced_loading: null
---

# 2. Publish your federation capability

## What you'll do

Three things in one publish:

1. Create the **SVCB + TXT records** in Route 53 (`_ip-reputation._mcp._agents.<sub>...`)
2. **Sign** the record with a JWS using your sandbox's EC P-256 key (so other federation members can verify it)
3. Reference the **externally-hosted cap doc** (MCP Server Card per SEP-1649, plus the policy doc) at `https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/`

## Load the env

```bash
source /opt/lab/lab.env
echo "subdomain  = ${SANDBOX_SLUG}.${ZONE}"
echo "cap base   = ${CAP_BASE_URL}"
echo "sign key   = ${SIGN_KEY}"
```

## Look at the public cap docs first

These are the same for every learner — hosted on a separate AWS account
on a public S3 bucket. Open them in your browser or curl:

```bash
# DNS-AID cap envelope (the document SVCB points at)
curl -s ${CAP_BASE_URL}/ip-reputation/v1.json | head -30

# MCP Server Card per SEP-1649 (model's view of the server's tools/capabilities)
curl -s ${CAP_BASE_URL}/ip-reputation/mcp-server-card.json | head -30

# Policy doc (rate limits, allowed methods, governance contacts)
curl -s ${CAP_BASE_URL}/ip-reputation/policy.json | head -30
```

Notice: these are **MCP server cards**, not A2A agent cards. The
`ip-reputation` capability is an MCP server (it exposes the `lookup_ip`
tool over Streamable HTTP). A2A `agent-card.json` is a different
discovery convention for peer-to-peer agents — we'll cover that in a
later lab if/when we add an A2A agent.

## Publish (signed, with cap_uri + policy_uri)

```bash
dns-aid publish \
    --name ip-reputation \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint agentgateway \
    --port 3000 \
    --transport streamable-http \
    --capability ip-reputation \
    --version 1.0.0 \
    --description "Threat-intel federation: IP reputation lookup" \
    --cap-uri    "${CAP_BASE_URL}/ip-reputation/v1.json" \
    --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json" \
    --sign \
    --private-key "${SIGN_KEY}"
```

What you just did:

- `--endpoint agentgateway --port 3000` → callable docker hostname inside the sandbox
- `--transport streamable-http` → plain HTTP (the lab gateway has no TLS)
- `--cap-uri …/v1.json` → DNS-AID's `key65400` points at the public cap doc
- `--policy-uri …/policy.json` → governance metadata (referenced by agents that respect policy)
- `--sign --private-key` → JWS signature using your per-sandbox EC P-256 key

## Verify

```bash
# 1. Public DNS — should now resolve via Cloudflare
dig +short SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
dig +short TXT  _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1   # JWS lives here

# 2. Local sandbox resolver (CoreDNS in docker, port 5353)
dig +short SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @127.0.0.1 -p 5353

# 3. dns-aid discover — fetches cap, verifies JWS, surfaces signer
dns-aid discover "${SANDBOX_SLUG}.${ZONE}"
```

The `dns-aid discover` output should now show:
- `endpoint: agentgateway:3000` (from your SVCB)
- `cap_uri: https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json` (resolves, fetches, JSON-parses)
- `signature_verified: true` + signer kid
- `policy_uri:` referenced

## Try it — publish a second one

The federation supports more capabilities. Try url-scanner (cap docs
for it land in S3 when you upload them; for now just publish a record):

```bash
dns-aid publish \
    --name url-scanner \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint agentgateway \
    --port 3000 \
    --transport streamable-http \
    --capability url-scanner \
    --description "Phishing / malware URL verdicts" \
    --sign --private-key "${SIGN_KEY}"
```

Then `dns-aid discover` again — see two agents now.

## Success

Auto-completes when at least one signed `_ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` SVCB record resolves.
