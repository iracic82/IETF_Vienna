# ip-reputation agent — DNS-AID cap docs

This directory ships the four documents that describe the `ip-reputation`
agent for the IETF_Vienna federation:

**This is an MCP server** (provides MCP tools). MCP servers ship the MCP
Server Card only — `agent-card.json` is for A2A protocol agents, not MCP.

| File | Format | Discovery convention |
|---|---|---|
| `mcp-server-card.json` | MCP SEP-1649 Server Card | `.well-known/mcp-server-card` on the MCP HTTP endpoint |
| `policy.json` | Custom policy doc | Referenced from `policy_uri` in DNS-AID cap |
| `v1.json` | DNS-AID cap-doc envelope (this version) | Referenced from SVCB `key65400` (cap_uri) |

## Why hosted externally

- **No SSRF blocks** — public HTTPS endpoint, dns-aid library happily fetches and verifies
- **Same content for all learners** — every Instruqt sandbox sees the same federation metadata
- **Real cap-sha256** — file is byte-stable on S3, sha256 in DNS matches forever
- **No per-sandbox TLS** — the lab's gateway runs HTTP-only; this is HTTPS via CloudFront

## Hosted at

```
https://cap.workshop.highvelocitynetworking.com/ip-reputation/v1.json
https://cap.workshop.highvelocitynetworking.com/ip-reputation/mcp-server-card.json
https://cap.workshop.highvelocitynetworking.com/ip-reputation/agent-card.json
https://cap.workshop.highvelocitynetworking.com/ip-reputation/policy.json
```

(See top-level `docs/caps/README.md` for the S3 + CloudFront setup.)

## How DNS-AID references it

```
dns-aid publish \
    --name ip-reputation \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint agentgateway \
    --port 3000 \
    --transport streamable-http \
    --capability ip-reputation \
    --cap-uri https://cap.workshop.highvelocitynetworking.com/ip-reputation/v1.json \
    --policy-uri https://cap.workshop.highvelocitynetworking.com/ip-reputation/policy.json \
    --sign \
    --private-key /opt/lab/keys/agent-signing.pem
```
