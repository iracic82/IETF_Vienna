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
  title: Terminal 1
  type: terminal
  hostname: host
- id: ibaxreqghtpv
  title: Terminal 2
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

# 2. Publish — DNS becomes a gateway route in seconds

## What you'll do

One `dns-aid publish` command writes a SVCB + a few TXT records to
Route 53. Three things will happen as a consequence:

1. **The capability becomes discoverable** by any agent who knows
   the federation's naming convention (`_<name>._<proto>._agents.<zone>`).
2. **The published cap_uri + policy_uri** point at the contract on S3.
   In C3 the agent will fetch both: cap doc to know what tools are
   available, policy doc for the SDK caller-side enforcement check.
3. **The xDS translator** notices the new SVCB on its next poll and
   pushes a `Route` + `Backend` to agentgateway via Envoy v3 ADS.
   No human edits agentgateway's config. The route just appears.

## The architecture you're operating

```
   dns-aid publish ip-reputation         ┌──────────────────────┐
        │                       ┌──────► │ fastmcp-ip-reputation│
        ▼                       │        └──────────────────────┘
   ┌──────────┐  poll SVCB  ┌───┴─────┐
   │ Route 53 │ ──────────► │translator│  Envoy v3 ADS (Delta gRPC)
   │  lab.    │             │ ADS :18000 │ ◄── continuously open stream
   │  ccdes-  │             │          │     no gateway restart needed
   │  anity   │             └────┬─────┘
   │  .com    │                  │  push: Bind / Listener / Route / Backend
   └─┬────────┘                  ▼
     │                     ┌──────────────┐
     │  cap_uri + policy   │ agentgateway │ ← 0 routes at boot
     │  references (TXT)   │ xdsAddress:↑ │   1 route after publish
     │                     └──────┬───────┘
     ▼                            │  POST /ip-reputation/mcp
   ┌──────────────────────┐       ▼
   │  S3 cap docs         │   ┌─────────┐
   │  - v1.json (envelope)│   │ caller  │ (Strands/Gemini agent in C3,
   │  - mcp-server-card   │   │  or any │  or curl, or any MCP client)
   │  - policy.json       │   │  client │
   └──────────────────────┘   └─────────┘
       ▲     ▲
       │     │  fetched by SDK caller-side
       │     │  guard before invocation
       │     │  (C3 audit trail shows it)
```

## Read the contract first — three published documents

These three JSONs are hosted on a public S3 bucket. The DNS record you
publish will point at them via `--cap-uri` / `--policy-uri`. Read them
before publishing so you know what you're advertising:

```run
source /opt/lab/lab.env

# 1. DNS-AID cap envelope (the document SVCB's cap_uri points at)
curl -s ${CAP_BASE_URL}/ip-reputation/v1.json | head -30

# 2. MCP Server Card per SEP-1649 (the tool catalogue the model uses)
curl -s ${CAP_BASE_URL}/ip-reputation/mcp-server-card.json | head -30

# 3. Policy doc (what the SDK caller-side guard evaluates pre-invocation)
curl -s ${CAP_BASE_URL}/ip-reputation/policy.json | head -30
```

What each document is for:

| Document | Discovery role | Enforcement role |
|---|---|---|
| `v1.json` (cap envelope) | Tells the caller this is an MCP server, points at MCP card + policy | — |
| `mcp-server-card.json` ([SEP-1649](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1649)) | Tool list, schemas, transport — what the model can call | — |
| `policy.json` | — | **Read by the SDK caller-side guard** before invocation (allowed_methods, allowed_tools, rate_limits, telemetry contract) and by the **target-side ASGI middleware** on every incoming request |

> **Why MCP card, not A2A agent card?** ip-reputation is an MCP server
> exposing the `lookup_ip` tool over Streamable HTTP. A2A's
> `agent-card.json` is a different convention for peer-to-peer agents
> — not applicable here.

## Watch the translator + the gateway live

You have **two terminal tabs** (Terminal 1 + Terminal 2) so you can
publish in one and watch live updates in the other.

In **Terminal 2** — watch the translator:

```run
docker logs -f translator
```

Back in **Terminal 1** you'll run the publish next. (Optionally you
can use a `watch` loop in Terminal 2 to see the gateway routes update
in real time:)

```run
watch -n 1 'curl -s http://localhost:15000/api/routes 2>/dev/null | jq "{routes: [.[].route_name]}" 2>/dev/null'
```

Right now both panes show **0 routes**. The translator is polling DNS,
finds nothing, pushes empty snapshots.

## Publish — one DNS record, one route appears

```run
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
    --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json" \
    --ttl 30
```

> **Why `--ttl 30`:** when you delete this record later (the C3 demo
> punchline), downstream resolvers (1.1.1.1, 9.9.9.9, local CoreDNS)
> keep serving the cached answer until the TTL expires. With the
> default TTL=3600, a delete would take an hour to propagate —
> invisible in a demo. TTL=30 means caches refresh every ~30s and
> "delete → route vanishes" lands within a minute. Production
> federations typically use 300–3600s to reduce DNS load.

What just happened, in order:

1. **dns-aid serialised the record** (SVCB with standard SvcParams +
   custom dnsaid_key65400/65403 for cap_uri/policy_uri, demoted to
   TXT because Route 53 doesn't support custom SVCB SvcParams yet).
2. **dns-aid called Route 53** via `ChangeResourceRecordSets`.
3. **Route 53 propagated** to its 4 authoritative name servers in
   seconds.
4. **The translator's next poll cycle** (≤5s) finds the new SVCB.
5. **The translator encodes** a `Bind` + `Listener` + `Route` +
   `Backend` as Envoy v3 ADS resources and pushes them to
   agentgateway over the open Delta stream.
6. **The gateway materialises** the new route. Now POST `/ip-reputation/mcp`
   on port 3000 proxies to `fastmcp-ip-reputation:3000/mcp` for any
   client — agent, curl, or browser.

> **Why no `--sign` in this lab?** dns-aid supports JWS-signed
> records (ECDSA P-256, signer kid in JWKS). On Route 53 the
> signed token gets demoted to TXT, and the encoded JWS exceeds
> Route 53's 255-char-per-string TXT limit. dns-aid v0.21 doesn't
> yet auto-chunk long TXT values, so we publish unsigned. C3's
> audit chain reports this honestly as "JWS signature: not signed
> (cap doc unsigned)" — we don't pretend the trust gap isn't there.

## Verify the public DNS layer

> **Tip on `dig +short SVCB`:** some resolvers (notably Cloudflare 1.1.1.1)
> return SVCB rdata in a binary form that `+short` doesn't pretty-print.
> Use `+noall +answer` for consistent output everywhere.

Run these three checks. Each one validates a different layer of the
discovery story.

### Check 1 — the SVCB itself is resolvable from a public resolver

```run
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
```

Expected output:
```
_ip-reputation._mcp._agents.<slug>.lab.ccdesanity.com. 30 IN SVCB 1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000
```

What each field means:

| Field | Value | Means |
|---|---|---|
| `30` | TTL | Cached for 30s at downstream resolvers (set by `--ttl 30`) |
| `SVCB 1` | RR type + priority | Standard [RFC 9460](https://datatracker.ietf.org/doc/rfc9460/) SVCB, priority 1 |
| `fastmcp-ip-reputation.` | target host | Where the actual MCP backend lives. The xDS translator reads THIS to wire the gateway's `Backend` resource. |
| `mandatory=alpn,port` | required SvcParams | Clients MUST honour these or treat the record as broken |
| `alpn="mcp"` | application protocol | This endpoint speaks MCP (not h2, not http/1.1) |
| `port=3000` | port | Backend listens on 3000 |

### Check 2 — DNSSEC chain validates from root

```run
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

```run
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

The `dnsaid_key65400=...` line is your cap doc URL — the agent in C3
will fetch this from S3 as part of its trust check. The `dnsaid_key65403=...`
line is the policy URL — what the **SDK caller-side guard** evaluates
before letting the agent invoke `lookup_ip`.

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

## Verify the xDS layer caught up + warm up the gateway

Within ~10 seconds of publishing, the gateway should have the route.
Run the verify-curl below — it does two things:
  1. Confirms the data plane is actually serving the route (HTTP 200).
  2. **Warms up** the MCP session path. The very first request through
     a freshly-materialised route can flake with "Invocation failed"
     because the agentgateway↔fastmcp MCP handshake races with route
     activation. By running curl first, we prime the path so C3's
     agent invocation succeeds first try.

```run
sleep 8
curl -s http://localhost:15000/config_dump | python3 -c "import json,sys; d=json.load(sys.stdin); ls=list(d.get('binds',[{}])[0].get('listeners',{}).values()); print('routes:  ', list((ls[0] if ls else {}).get('routes',{}).keys()) if ls else 'no listeners'); print('backends:', len(d.get('backends',[])))"

# Warm up the MCP route — should print HTTP 200
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

```run
dns-aid discover "${SANDBOX_SLUG}.${ZONE}"
```

Shows the agent record from DNS, including the cap_uri (S3 URL) and
policy_uri. The agent in C3 will fetch these.

> **You'll see a yellow warning** like:
> ```
> [warning] Agent Card URL blocked by SSRF protection
>           error="Cannot resolve hostname 'fastmcp-ip-reputation' …"
>           url=https://fastmcp-ip-reputation/.well-known/agent-card.json
> ```
> This is harmless. dns-aid tries to fetch the optional A2A
> `agent-card.json` from the SVCB target host. The target name only
> resolves inside the docker network (it's the backend container
> name), so dns-aid's safety check refuses the fetch — and falls
> back to the TXT/cap_uri data, which is what we actually use.
> The CLI's job is done; discovery completed with `agents_found=1`.

## Try the demo's punchline — delete and watch the route vanish

> ⚠️ This deletes the record you just published. You'll need to
> re-publish before moving to C3. Skip this if you want to keep moving.

```run
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
