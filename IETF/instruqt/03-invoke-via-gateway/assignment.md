---
slug: invoke-via-gateway
id: uno7yiytzyew
type: challenge
title: 3. Invoke — agent discovers, verifies, calls. Full trust chain.
teaser: Watch the AI agent discover via DNS, fetch the cap doc from S3, verify DNSSEC,
  and invoke through the gateway.
notes:
- type: text
  contents: |-
    Now the payoff. The AI agent has been waiting with nothing to
    discover. Ask it about an IP. It will use DNS-AID to find a
    capability it didn't ship with, fetch the published contract from
    S3, check DNSSEC validation, invoke through the gateway, and
    return both the verdict and a complete audit chain.

    Everything you see in the terminal happens because of DNS records —
    not because anything was hardcoded in the agent.
tabs:
- id: 0xjpwr7dduro
  title: Terminal
  type: terminal
  hostname: host
- id: 2r8mrjsmdsto
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: bfwf3ubokb9x
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
- id: yqjcx0qn49ao
  title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# 3. Invoke — agent discovers, verifies, calls

## Start the agent

```bash
docker exec -it strands-agent python /app/agent.py
```

You'll see a banner and the `analyst>` prompt. The agent is a Vertex
Gemini model with 20 dns-aid MCP tools loaded. It has no built-in
knowledge of any IP — every fact must come from a tool call.

## Ask a real question

```
analyst> Is 185.220.101.45 malicious?
```

Watch the terminal as the agent works. You'll see exactly this sequence:

```
  [tool] discover_agents_via_dns({'name': 'ip-reputation', 'domain': '<slug>.lab.ccdesanity.com', ...})
  [cap-fetch] GET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json
  [dnssec]   _ip-reputation._mcp._agents.<slug>.lab.ccdesanity.com → ad
  [tool] call_agent_tool({tool_name: 'lookup_ip', endpoint: 'http://agentgateway:3000/ip-reputation/mcp', arguments: {ip: '185.220.101.45'}})
  [result] {"verdict":"malicious","confidence":0.95,"sources":["tor-exit-list","abuse.ch"]}

agent> **Verdict:** malicious
       **Confidence:** 0.95
       **Sources:** ['tor-exit-list', 'abuse.ch']
       **Trust chain (audit):**
       - SVCB record: _ip-reputation._mcp._agents.<slug>.lab.ccdesanity.com
       - DNSSEC: validated (AD flag set on SVCB query against 1.1.1.1)
       - JWS signature: not signed (cap doc unsigned)
       - Cap doc: https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json
                  (fetched, agent=ip-reputation, version=1.0.0)
       - Policy: https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy.json
       - Invoked via: http://agentgateway:3000/ip-reputation/mcp
```

## What each line of that audit chain tells you

| Line | Source of truth | Verified how |
|---|---|---|
| `SVCB record` | Public DNS | Any analyst can `dig` it themselves |
| `DNSSEC: validated` | Cryptographic chain root → .com → ccdesanity.com → lab.ccdesanity.com | `dig +dnssec` returned the **AD flag** |
| `JWS signature` | Would-be ECDSA P-256 sig on the cap doc | Honest report: lab publishes unsigned because Route 53 can't fit the JWS in a single TXT string |
| `Cap doc` | S3 public bucket, fetched live | The wrapper GET'd it and parsed it |
| `Policy` | Same S3 bucket | Referenced in the cap doc, available for any policy enforcer |
| `Invoked via` | agentgateway path | Visible in the gateway's request log |

**No piece of this audit chain comes from training data.** Each line
corresponds to a verifiable observation.

## Try a known-clean IP

```
analyst> What about 8.8.8.8?
```

Should return clean with confidence 0.99, source `google-public-dns`.

## Try the DNS-AID Explorer tab

Open the **DNS-AID Explorer** tab. While the agent runs you should see
the flow graph animate through:

1. Strands agent picks `discover_agents_via_dns`
2. dns-aid MCP → CoreDNS → Route 53 (SVCB lookup)
3. Wrapper fetches cap doc from S3
4. Wrapper checks DNSSEC AD flag via Cloudflare
5. Agent picks `call_agent_tool` for `lookup_ip`
6. agentgateway routes to `fastmcp-ip-reputation:3000`
7. Tool result returned with full audit

Click any step in the flow graph — the right panel shows the actual
request/response for that step.

## Tour the agentgateway UI

Open the **agentgateway UI** tab. There are five pages worth visiting,
and one banner worth re-reading.

### 🟣 The banner at the top of every page

> *"Configuration is managed by an external source (XDS). Editing the
> configuration is not allowed via the UI."*

This is THE proof of the architecture. Every other gateway UI you've
ever seen lets you click "Add Route" or edit config. This one doesn't.
The gateway is admitting: "my routes are pushed to me by xDS — I don't
own them." DNS is the source of truth.

### Home

Sidebar shows: **Listeners 1**, **Routes 1**, **Backends 1**, **Policies 1**.

That `1 route` and `1 backend` came from your `dns-aid publish` in C2.
Delete the DNS record → numbers tick back to 0 within 5s.

### Routes

Click `ip-reputation-mcp`. You'll see:

| Field | Value |
|---|---|
| Listener | `dnsaid-discovered` (the translator named it this) |
| Port | 3000 |
| Route Pattern | `/ip-reputation/mcp` *(exact match)* |
| Backends | `fastmcp-ip-reputation:3000` |

No human typed any of that. The translator built it from your SVCB
record and pushed it via xDS Delta.

### Backends

The backend `fastmcp-ip-reputation:3000` is here, but **the UI shows it
labeled as "Unknown Backend" with Type "Unknown"** — that's an upstream
agentgateway UI bug, not a problem with the backend itself.

To see the real backend data the runtime knows about, hit the admin API:

```bash
curl -s http://localhost:15000/config_dump | python3 -m json.tool
```

In that JSON you'll see entries like:

```json
"backends": [
  {
    "backend": {
      "mcp": {
        "name": "ip-reputation-mcp",
        "namespace": "default",
        "target": {
          "targets": [
            { "name": "ip-reputation",
              "mcp": { "backend": { "backend": "dnsaid-upstream-ip-reputation" },
                       "path": "/mcp" }}
          ]
        }
      }
    }
  }
]
```

So the **MCP backend wrapping** the **static upstream** is correctly
configured and named — the runtime sees it, the gateway routes through
it, the proxy works. The "Unknown" label is purely a UI display bug
(it walks `backend.mcp` instead of `backend.backend.mcp` and falls
through to the default).

**Trace the chain**: `dig SVCB ...` → SVCB target field → translator
discovers it → translator pushes the Backend via xDS → gateway
materializes it → `config_dump` shows it → invocation works through it.

### Playground (currently broken on xDS-bound routes)

The Playground tab is meant to let you test routes interactively, but
it's broken when routes are pushed via xDS — the UI derives its
request URL from the bind host (`0.0.0.0` → displayed as `*`), and
the browser rejects `http://*:3000/...` as `Invalid name`. Skip it.

### Use curl from the Terminal tab instead

Same round trip the AI agent uses, no broken UI:

```bash
# 1. MCP initialize — proves the route works end-to-end
curl -sw '\nHTTP %{http_code}\n' \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -H 'mcp-protocol-version: 2025-03-26' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'

# 2. Real tool call — get a verdict for a known-bad IP
curl -s \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -H 'mcp-protocol-version: 2025-03-26' \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_ip","arguments":{"ip":"185.220.101.45"}}}' \
    | python3 -m json.tool
```

The second call returns the same verdict object the AI agent gets in C3
(`verdict: malicious, confidence: 0.95, sources: tor-exit-list, abuse.ch`).
This proves the DNS publish → translator → xDS → gateway → backend
round trip works without any AI involved.

### CEL Playground (foreshadowing)

CEL = Common Expression Language. agentgateway can apply CEL filters
to incoming requests. In IETF2 (the workshop) we'll use this to enforce
the policy.json contract — for example, `request.method == "POST" &&
request.path == "/ip-reputation/mcp" && request.headers["authorization"] != ""`.
For now it's empty; in the workshop you'll write some.

## The big takeaway

This route exists because of a DNS record. Try the demo punchline:

```bash
# One-shot delete (pulled from the repo so terminal paste can't mangle
# multi-line bash). Deletes the SVCB + TXT records for ip-reputation.
curl -sSL https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/scripts/delete-ip-reputation-record.sh | bash

# Within ~5s the translator notices the absence and removes the route.
# Refresh the agentgateway UI Routes page: count 1 → 0.
# Re-publish (C2 publish command) to continue with C3.
```

## Bonus 1 — compare resolvers side by side

```bash
source /opt/lab/lab.env

for r in 1.1.1.1 9.9.9.9 8.8.8.8; do
    printf "%-10s " "$r"
    dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @$r | tail -1
done

# DNSSEC AD flag — all three should return 'ad' in flags
for r in 1.1.1.1 9.9.9.9 8.8.8.8; do
    printf "%-10s " "$r"
    dig +dnssec SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @$r +noall +comments | grep 'flags:'
done
```

This is the cryptographic chain working — same record, same signature,
validated by three independent resolvers.

## Bonus 2 — what happens if you ask about a totally unknown IP

```
analyst> Is 203.0.113.99 malicious?
```

The lookup DB doesn't know about that IP. Watch the agent honestly
report `verdict: unknown` (not "probably safe" or "I'll guess from
training"). Honest reporting is part of the federation contract.

## The DAWN argument, in one paragraph

You just watched an AI agent **discover** a capability via standards-based
DNS (no SDK, no registry), **verify** its authenticity (DNSSEC chain to
root + cryptographic cap doc available), and **invoke** through a
runtime enforcement layer (agentgateway with xDS-driven routes). The
agent never knew the endpoint before the question was asked. It only
knew the naming convention. **Discovery, identity, and policy are
separate layers — governed at different times, by different teams,
using protocols that already exist.** That's the DAWN argument made
literal.

## Success

Auto-completes after at least one successful `lookup_ip` tool call
through the federation.
