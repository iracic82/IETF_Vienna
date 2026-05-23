---
slug: publish-your-agent
id: 2kfzxpqcouix
type: challenge
title: 2. Publish your federation capability
teaser: Publish the ip-reputation DNS-AID record pointing at externally-hosted cap
  docs in S3.
notes:
- type: text
  contents: |-
    You publish — by hand — the DNS-AID record that lets other
    federation members discover your capability. The record points at
    a cap doc + MCP Server Card + policy doc hosted publicly on S3 —
    the same docs every other learner sees. dns-aid talks to Route 53
    directly using the Instruqt-injected secrets.

    Note on JWS signing: this lab uses Route 53, which doesn't support
    custom SVCB SvcParams (key65400/65403/65405), so dns-aid demotes
    those to TXT records. JWS tokens exceed 255 chars and trigger a
    Route-53 limit, so signing is omitted in this lab. We discuss the
    "would-be signed" trust chain honestly in challenge 3.
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
timelimit: 1800
enhanced_loading: null
---

# 2. Publish your federation capability

## What you'll do

1. Create the **SVCB + TXT records** in Route 53 (`_ip-reputation._mcp._agents.<sub>...`)
2. Reference the **externally-hosted cap doc** (MCP Server Card per SEP-1649, plus the policy doc) at `https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/`

> Why no JWS in this lab? Route 53 doesn't support custom SVCB SvcParams,
> so cap_uri / policy_uri / JWS are demoted to TXT. The JWS token is
> >255 chars and trips Route 53's per-string TXT limit. dns-aid v0.21
> doesn't auto-chunk TXT yet, so we publish unsigned. The audit chain
> in challenge 3 reports this honestly as "JWS signature: not signed".

## Load the env

```bash
source /opt/lab/lab.env
echo "subdomain  = ${SANDBOX_SLUG}.${ZONE}"
echo "cap base   = ${CAP_BASE_URL}"
```

## Look at the public cap docs first

These are the same for every learner — hosted on a separate AWS account
on a public S3 bucket. Open them in your browser or curl:

```bash
# DNS-AID cap envelope (the document SVCB points at via cap_uri)
curl -s ${CAP_BASE_URL}/ip-reputation/v1.json | head -30

# MCP Server Card per SEP-1649 (model's view of the server's tools)
curl -s ${CAP_BASE_URL}/ip-reputation/mcp-server-card.json | head -30

# Policy doc (rate limits, allowed methods, governance contacts)
curl -s ${CAP_BASE_URL}/ip-reputation/policy.json | head -30
```

Notice: these are **MCP server cards**, not A2A agent cards. The
`ip-reputation` capability is an MCP server (it exposes the `lookup_ip`
tool over Streamable HTTP). A2A `agent-card.json` is a different
discovery convention for peer-to-peer agents — not applicable here.

## Publish

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
    --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json"
```

What you just did:

- `--endpoint agentgateway --port 3000` → callable docker hostname inside the sandbox
- `--transport streamable-http` → plain HTTP (the lab gateway has no TLS)
- `--cap-uri …/v1.json` → DNS-AID's `key65400` points at the public cap doc
- `--policy-uri …/policy.json` → governance metadata (referenced by agents that respect policy)

## Verify

```bash
# 1. Public DNS — Cloudflare, Quad9, Google — all should return the SVCB
echo "── Cloudflare ──"
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1

echo "── Quad9 ──"
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @9.9.9.9

echo "── Google ──"
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @8.8.8.8

# 2. Cap_uri + policy_uri travel as TXT (Route 53 demotes from SVCB)
dig +short TXT _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
# You should see: capabilities=, version=, description=, dnsaid_key65400=…cap doc URL,
#                 dnsaid_key65403=…policy URL

# 3. Local sandbox resolver (CoreDNS in docker, host port 5353)
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @127.0.0.1 -p 5353

# 4. dns-aid discover — fetches cap, surfaces parsed structure
dns-aid discover "${SANDBOX_SLUG}.${ZONE}"
```

The `dns-aid discover` output should show:
- `endpoint: agentgateway:3000` (from your SVCB)
- `cap_uri: https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json` (fetches + JSON-parses)
- `policy_uri:` referenced
- `signature_verified: false` (this lab publishes unsigned — see note at top)

## Why dig +noall +answer instead of +short

Some resolvers (notably Cloudflare 1.1.1.1) return SVCB rdata in a
format that `dig +short` doesn't pretty-print. The record is *present*
— look at the header `ANSWER: 1` — but `+short` shows nothing. Using
`+noall +answer` works uniformly across Cloudflare, Quad9, and Google.

## Success

Auto-completes when `_ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` SVCB record resolves on the public DNS.
