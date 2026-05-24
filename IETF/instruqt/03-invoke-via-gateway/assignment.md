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

```run
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

Open the **agentgateway UI** tab. Five sidebar pages to visit, plus
one banner at the top that's worth re-reading.

### 🟣 The purple banner

> *"Configuration is managed by an external source (XDS). Editing the
> configuration is not allowed via the UI."*

This is THE proof of the architecture. Every other gateway UI you've
ever seen lets you click "Add Route" / "Add Backend". This one doesn't —
the buttons are greyed out. The gateway is openly admitting: "my topology
comes from xDS, I don't own it." DNS is the source of truth.

### Listeners

```
1 port bind  •  1 listener
Port 3000
  Name        Protocol  Hostname  Endpoint         Backends    TLS    Policies
  listener-1  HTTP      *         http://*:3000    1 backend   TLS    View Policies
   (unnamed)
```

That `listener-1` was pushed by the xDS translator. The `*` hostname
means the listener accepts all virtual hosts (path-mode routing).

### Routes

```
1 HTTP route  •  0 TCP routes  •  1 bind with routes
Port 3000 (1 HTTP)
  Name           Type   Listener  Hostnames   Path                Backends
  ip-reputation  HTTP   unnamed   *           = /ip-reputation/mcp  1 backend
```

The `=` before `/ip-reputation/mcp` means **exact match** (not prefix).
Translator generates this from the SVCB `_ip-reputation._mcp._agents`
record — no human typed it.

### Backends

```
1 total backend
Port 3000  •  1 UNKNOWN
  Name              Type      Listener  Route          Weight
  Unknown Backend   Unknown   unnamed   ip-reputation  1
```

The route IS attached to a backend (the proxy works — you just saw it
in C3 above), but the UI shows `Name: Unknown Backend` and `Type:
Unknown` because of an upstream UI bug. To see the real data:

```run
curl -s http://localhost:15000/config_dump | python3 -m json.tool
```

You'll see the MCP-wrapper backend properly named `ip-reputation-mcp`,
the static backend named `dnsaid-upstream-ip-reputation`, and the
target list pointing at the actual fastmcp container. The runtime is
correct; only the UI label is wrong.

**Trace the chain**: `dig SVCB ...` → SVCB target field → translator
polls it → translator pushes Backend via xDS → gateway materializes
it → `config_dump` shows it → your invocation in C3 routed through it.

### Policies

```
Applied policies (non-inline)
  No non-route applied policies found.

Port 3000  •  1 route available
  Route          Type   Listener   Path/Hostnames        Policies
  ip-reputation  HTTP   Unnamed    /ip-reputation/mcp    0 policies
```

The "0 policies" count is misleading — the CORS policy IS attached
inline to the route (visible in `config_dump` under
`routes[].inlinePolicies[].cors`), but the UI counts it as 0 because
it only counts "non-inline" attached policies (a separate object type
not used here). This is another agentgateway UI nuance, not a missing
policy. Verify the CORS works:

```run
curl -i -X OPTIONS http://localhost:3000/ip-reputation/mcp \
    -H "Origin: http://localhost:15000" \
    -H "Access-Control-Request-Method: POST" 2>&1 | head -12
# Look for access-control-allow-origin: * in the response
```

### Playground (currently broken on xDS-bound routes)

The Playground tab is meant to let you test routes interactively, but
it's broken when routes are pushed via xDS — the UI derives its
request URL from the bind host (`0.0.0.0` → displayed as `*`), and
the browser rejects `http://*:3000/...` as `Invalid name`. Skip it.

### Use curl from the Terminal tab instead

Same round trip the AI agent uses, no broken UI:

```run
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

```run
# One-shot delete (pulled from the repo so terminal paste can't mangle
# multi-line bash). Deletes the SVCB + TXT records for ip-reputation.
curl -sSL https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/scripts/delete-ip-reputation-record.sh | bash

# Within ~5s the translator notices the absence and removes the route.
# Refresh the agentgateway UI Routes page: count 1 → 0.
# Re-publish (C2 publish command) to continue with C3.
```

## Bonus 1 — compare resolvers side by side

```run
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
