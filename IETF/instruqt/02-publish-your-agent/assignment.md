---
slug: publish-your-agent
id: 2kfzxpqcouix
type: challenge
title: 2. Publish — DNS becomes a gateway route in 5 seconds
teaser: Publish one DNS-AID record. Watch the agentgateway dynamically pick up the
  route via xDS.
notes:
- type: text
  contents: |-
    You're going to do something that looks ordinary but is anything but:
    create a DNS record. In five seconds, the agentgateway's route table
    will change without anyone touching its config. That's the entire
    point of this lab — DNS as the runtime control plane for AI agent
    federations.
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
- id: o9wteoifn4y8
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
- id: qtwx3muuwfqo
  title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# 2. Publish — DNS becomes a gateway route in 5 seconds

## The architecture you're operating

```
   dns-aid publish ip-reputation       ┌──────────────────────┐
        │                       ┌─────►│ fastmcp-ip-reputation│
        ▼                       │      └──────────────────────┘
   ┌──────────┐ poll SVCB  ┌────┴────┐
   │ Route 53 │ ─────────► │ translator │  Envoy v3 ADS gRPC
   │  (lab.   │            │            │ ◄─── stream open continuously
   │   ccdes  │            │ ADS :18000 │      no restart, no outage
   │   anity) │            └─────┬──────┘
   └──────────┘                  │ Delta push on every snapshot change
                                 ▼
                          ┌──────────────────┐
                          │  agentgateway    │ ← starts with 0 routes
                          │  xdsAddress: ↑   │   after publish: 1 route
                          └────────┬─────────┘
                                   │ POST /ip-reputation/mcp
                                   ▼
                           agent (or curl, or any MCP client)
```

## Inspect the published-contract documents

These live on S3 — the same docs every learner uses. The DNS-AID record
you're about to publish will point at them. Read them first so you
know what you're advertising:

```bash
source /opt/lab/lab.env

# DNS-AID cap envelope (referenced by SVCB key65400 / TXT fallback)
curl -s ${CAP_BASE_URL}/ip-reputation/v1.json | head -30

# MCP Server Card per SEP-1649 (model's view of the server's tools)
curl -s ${CAP_BASE_URL}/ip-reputation/mcp-server-card.json | head -30

# Policy doc (rate limits, allowed methods, governance contacts)
curl -s ${CAP_BASE_URL}/ip-reputation/policy.json | head -30
```

> **Why MCP card, not A2A agent card?** ip-reputation is an MCP server
> exposing the `lookup_ip` tool over Streamable HTTP. A2A `agent-card.json`
> is a different convention for peer-to-peer agents — not used here.

## Watch the translator + the gateway live

Open **two terminal panes** if you can (Terminal tab has split support).

Pane 1 — watch the translator:

```bash
docker logs -f translator
```

Pane 2 — watch the gateway routes update:

```bash
watch -n 1 'curl -s http://localhost:15000/api/routes 2>/dev/null | jq "{routes: [.[].route_name]}" 2>/dev/null'
```

Right now both panes show **0 routes**. The translator is polling DNS,
finds nothing, pushes empty snapshots.

## Publish — one DNS record, one route appears

```bash
dns-aid publish \
    --name ip-reputation \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint fastmcp-ip-reputation \
    --port 3000 \
    --transport streamable-http \
    --capability ip-reputation \
    --version 1.0.0 \
    --description "Threat-intel federation: IP reputation lookup" \
    --cap-uri    "${CAP_BASE_URL}/ip-reputation/v1.json" \
    --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json"
```

What just happened, in order:

1. **dns-aid signed your record locally** (well — it would have, if Route 53
   supported chunked TXT > 255 chars; we publish unsigned for now and report
   the gap honestly in C3's audit chain).
2. **dns-aid called Route 53** via `route53:ChangeResourceRecordSets` API.
3. **Route 53 propagated** to its 4 authoritative name servers in seconds.
4. **The translator's next poll cycle** (≤5s) finds the SVCB record.
5. **The translator encodes** a `Backend` + `Route` + `Listener` + `Bind`
   into protobuf, opens a Delta xDS push to agentgateway.
6. **The gateway materializes** the new route. Now `/ip-reputation/mcp`
   resolves to `fastmcp-ip-reputation:3000` from any client.

## Verify the public DNS layer

> **Tip on `dig +short SVCB`:** some resolvers (notably Cloudflare 1.1.1.1)
> return SVCB rdata in a binary form that `+short` doesn't pretty-print.
> Use `+noall +answer` for consistent output everywhere.

Run these three checks. Each one validates a different layer of the
discovery story.

### Check 1 — the SVCB itself is resolvable from a public resolver

```bash
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
```

Expected output:
```
_ip-reputation._mcp._agents.<slug>.lab.ccdesanity.com. 3600 IN SVCB 1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000
```

What each field means:

| Field | Value | Means |
|---|---|---|
| `3600` | TTL | Cached for 1 hour at downstream resolvers |
| `SVCB 1` | RR type + priority | Standard SVCB record, priority 1 |
| `fastmcp-ip-reputation.` | target host | Where the actual MCP backend lives. The xDS translator uses THIS to wire the gateway's route. |
| `mandatory=alpn,port` | required SvcParams | Clients MUST honour these |
| `alpn="mcp"` | protocol | This endpoint speaks MCP (not h2, not http/1.1) |
| `port=3000` | port | Backend listens on 3000 |

### Check 2 — DNSSEC chain validates from root

```bash
dig +dnssec SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1 +noall +comments | grep flags
```

Expected output:
```
;; flags: qr rd ra ad; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1
```

The crucial bit is **`ad`** — Authenticated Data. That means Cloudflare
walked the full chain `.` → `.com` → `ccdesanity.com` → `lab.ccdesanity.com`
and cryptographically verified every signature back to the IANA root
trust anchor. No `ad` flag = chain didn't validate.

`ANSWER: 2` means you got both the SVCB record AND its RRSIG signature.

### Check 3 — cap_uri + policy_uri travel as TXT records

Route 53 doesn't support custom SVCB SvcParams (key65400 / key65403), so
dns-aid demotes those to TXT records. This is where the cap doc URL and
policy URL live.

```bash
dig +short TXT _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
```

Expected output:
```
"version=1.0.0"
"capabilities=ip-reputation"
"description=Threat-intel federation: IP reputation lookup"
"dnsaid_key65400=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json"
"dnsaid_key65403=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy.json"
```

The `dnsaid_key65400=...` line is your cap doc URL. The agent in C3
will fetch this from S3 as part of its trust check.

> **Real-world caveat on DNS caching:** if you ever notice the gateway
> taking longer than 5s to pick up a newly published agent, you're
> hitting **negative caching at the public resolver**. Most resolvers
> (including 1.1.1.1) cache NXDOMAIN responses for the duration of the
> parent zone's SOA *minimum* field — typically 5–15 minutes. If a
> resolver queried for an agent BEFORE you published it, it'll keep
> serving NXDOMAIN until that cache expires.
>
> **In this lab the translator polls the local CoreDNS resolver** (which
> has no negative-cache pollution from earlier queries), so publish →
> route-materialized usually happens in <10s. In a production federation,
> design with this caching window in mind.

## Verify the xDS layer caught up

Within 5 seconds of publishing, the gateway should have a route:

```bash
sleep 6
curl -s http://localhost:15000/api/routes | jq .

# Or — try invoking. Now returns 200 instead of 404.
curl -sw '\nHTTP %{http_code}\n' \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -H 'mcp-protocol-version: 2025-03-26' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0"}}}'
```

Open the **agentgateway UI** tab → Routes section. You'll see
`/ip-reputation/mcp` with backend `fastmcp-ip-reputation:3000`. **No
human edited this config.** The DNS record + the translator did it.

## Inspect the discovery view

```bash
dns-aid discover "${SANDBOX_SLUG}.${ZONE}"
```

Shows the agent record from DNS, including the cap_uri (S3 URL) and
policy_uri. The agent in C3 will fetch these.

## Try the demo's punchline — delete and watch the route vanish

> ⚠️ This deletes the record you just published. You'll need to
> re-publish before moving to C3. Skip this if you want to keep moving.

```bash
# One-shot delete (pulled from the repo so terminal paste can't mangle
# multi-line bash). Deletes the SVCB + TXT records for ip-reputation.
curl -sSL https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/scripts/delete-ip-reputation-record.sh | bash

# Within ~5s the translator polls Route 53, sees the record is gone,
# and removes the route from agentgateway. Confirm with curl 404:
sleep 6
curl -sw '%{http_code}\n' -o /dev/null \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
# Expected: 404 (route was torn down)
```

That's the full story: DNS is the source of truth. Add a record →
runtime has it. Remove a record → runtime forgets.

## Re-publish if you deleted

Re-run the `dns-aid publish` command from the top of this challenge to
restore the record before moving to C3.

## Success

Auto-completes when the SVCB record resolves publicly. After publish,
proceed to C3.
