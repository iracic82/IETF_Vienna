---
slug: invoke-via-gateway-ard
id: f8yug5dffemf
type: challenge
title: 3. Invoke — same agent, two discovery paths, one trust chain
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
- id: teyxpndvbmgj
  title: Terminal
  type: terminal
  hostname: host
- id: c1fnu7srs8yf
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: vyshcyocngbv
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# 3. Invoke — agent discovers, verifies, calls

## Ask a real question

The agent is a Vertex Gemini model with 20 dns-aid MCP tools loaded.
It has no built-in knowledge of any IP — every fact must come from a
tool call. The command below starts the agent, pipes a single question
in, and prints the full reply — one-shot, so the terminal returns to
you when the answer arrives.

> [!IMPORTANT]
> The `ip-reputation` agent should already be published and discoverable
> from when you completed it in **Challenge 2**. If you skipped that
> step or restarted the lab, run the two blocks below before the agent
> command — otherwise the agent won't find a tool to call.
>
> Re-publish the `ip-reputation` record:
>
> ```run
> dns-aid publish \
>     --name ip-reputation \
>     --domain "${SANDBOX_SLUG}.${ZONE}" \
>     --protocol mcp \
>     --endpoint fastmcp-ip-reputation \
>     --port 3000 \
>     --transport streamable-http \
>     --capability ip-reputation \
>     --version 1.0.0 \
>     --description "Threat-intel federation: IP reputation lookup" \
>     --cap-uri    "${CAP_BASE_URL}/ip-reputation/v1.json" \
>     --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json" \
>     --ttl 30
> ```
>
> Then flush CoreDNS so the translator picks up the new record:
>
> ```run
> sudo docker restart coredns && sleep 3
> ```

```run
docker exec -i strands-agent python /app/agent.py <<< "Is 185.220.101.45 malicious?"
```

> **Want the interactive REPL instead?** Open a second terminal tab
> (top of the screen) and run `docker exec -it strands-agent python
> /app/agent.py` there — you'll get the `analyst>` prompt and can ask
> multiple questions in a session. Keep this tab free for the lab's
> `run` blocks.

Watch the terminal as the agent works. You'll see exactly this sequence:

```
  [tool] discover_agents_via_dns({'name': 'ip-reputation', 'domain': '<slug>.lab.ccdesanity.com', ...})
  [cap-fetch] GET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json
  [dnssec]   ip-reputation.<slug>.lab.ccdesanity.com → ad
  [tool] call_agent_tool({tool_name: 'lookup_ip', endpoint: 'http://agentgateway:3000/ip-reputation/mcp', arguments: {ip: '185.220.101.45'}})
  [result] {"verdict":"malicious","confidence":0.95,"sources":["tor-exit-list","abuse.ch"]}

agent> **Verdict:** malicious
       **Confidence:** 0.95
       **Sources:** ['tor-exit-list', 'abuse.ch']
       **Trust chain (audit):**
       - SVCB record: ip-reputation.<slug>.lab.ccdesanity.com
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

```run
docker exec -i strands-agent python /app/agent.py <<< "What about 8.8.8.8?"
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

![Listeners page](https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/IETF/instruqt/assets/c3/listeners.png)

`listener-1` was pushed by the xDS translator. The `*` hostname means
the listener accepts all virtual hosts (path-mode routing).

### Routes

![Routes page](https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/IETF/instruqt/assets/c3/routes.png)

The `=` before `/ip-reputation/mcp` means **exact match** (not prefix).
Translator generates this from your published SVCB record — no human
typed it.

### Backends

```
1 total backend
Port 3000  •  1 UNKNOWN
  Name              Type      Listener  Route          Weight
  Unknown Backend   Unknown   unnamed   ip-reputation  1
```

The route IS attached to a backend (the proxy works — you just saw it
in Challenge 3 above), but the UI shows `Name: Unknown Backend` and `Type:
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
it → `config_dump` shows it → your invocation in Challenge 3 routed through it.

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

# 2. Real tool call — get a verdict for a known-bad IP.
#
# MCP Streamable HTTP is session-bound: `initialize` returns an
# Mcp-Session-Id header that subsequent calls MUST echo back.
# (a) capture the session id from initialize response headers
# (b) reuse it in tools/call
# The response body is SSE (`data: {…}` per line) — strip the prefix
# before piping to json.tool.

SESSION_ID=$(curl -sD - -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -H 'mcp-protocol-version: 2025-03-26' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
    -o /dev/null | grep -i '^Mcp-Session-Id:' | awk '{print $2}' | tr -d '\r')

echo "session: ${SESSION_ID}"

curl -s -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -H 'mcp-protocol-version: 2025-03-26' \
    -H "mcp-session-id: ${SESSION_ID}" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_ip","arguments":{"ip":"185.220.101.45"}}}' \
    | sed -n 's/^data: //p' | python3 -m json.tool
```

The second call returns the same verdict object the AI agent gets in Challenge 3
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
curl -sSL https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/scripts/delete-ip-reputation-record.sh | bash
```

Within ~30s the translator notices the absence and removes the route.
Verify with a POST — should return `route not found`:

```run
curl http://localhost:3000/ip-reputation/mcp -X POST -H 'content-type:application/json' -d '{}'
```

Expected terminal output:

![Delete + 404 verification](https://raw.githubusercontent.com/iracic82/IETF_Vienna/main/IETF/instruqt/assets/c3/delete-vanish.png)

Refresh the **agentgateway UI Routes** page — Routes count 1 → 0.
Re-publish the Challenge 2 command to restore them before moving on.

## Bonus 1 — compare resolvers side by side

```run
source /opt/lab/lab.env
for r in 1.1.1.1 9.9.9.9 8.8.8.8; do
    printf "%-10s " "$r"
    dig +noall +answer SVCB ip-reputation.${SANDBOX_SLUG}.${ZONE} @$r | tail -1
done

# DNSSEC AD flag — all three should return 'ad' in flags
for r in 1.1.1.1 9.9.9.9 8.8.8.8; do
    printf "%-10s " "$r"
    dig +dnssec SVCB ip-reputation.${SANDBOX_SLUG}.${ZONE} @$r +noall +comments | grep 'flags:'
done
```

Expected output (note `ad` flag set on every resolver):

```
1.1.1.1    ip-reputation.<slug>.lab.ccdesanity.com. 30 IN SVCB 1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000
9.9.9.9    ip-reputation.<slug>.lab.ccdesanity.com. 30 IN SVCB 1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000
8.8.8.8    ip-reputation.<slug>.lab.ccdesanity.com. 30 IN SVCB 1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000
1.1.1.1    ;; flags: qr rd ra ad; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1
9.9.9.9    ;; flags: qr rd ra ad; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1
8.8.8.8    ;; flags: qr rd ra ad; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1
```

Two things to notice:

- **`ad` in every `flags:` line** — all three public resolvers
  independently validated the DNSSEC chain (root → `.com` →
  `ccdesanity.com` → your zone). No resolver trusts the record blindly.
- **`ANSWER: 2`** on the `+dnssec` query — the SVCB record **plus its
  RRSIG signature**. The signature travels alongside the record, which
  is what lets each resolver verify it. (The first loop, without
  `+dnssec`, shows just the one SVCB line per resolver.)

This is the cryptographic chain working — same record, same signature,
validated by three independent resolvers.

## Bonus 2 — what happens if you ask about a totally unknown IP

```run
docker exec -i strands-agent python /app/agent.py <<< "Is 203.0.113.99 malicious?"
```

The lookup DB doesn't know about that IP. Watch the agent honestly
report `verdict: unknown` (not "probably safe" or "I'll guess from
training"). Honest reporting is part of the federation contract.

## Bonus 2b — native ARD discovery through the same MCP tool (dns-aid 0.26.2)

You've seen the agent call `discover_agents_via_dns` to find
`ip-reputation` via the DNS-AID SVCB record. **dns-aid 0.26.2** made
the same MCP tool ARD-aware: pass `use_http_index=True` and it
resolves your `_catalog._agents.<domain>` SVCB pointer (published
in C2), fetches the ARD `ai-catalog.json`, dereferences each entry's
agent card, and returns agents WITH their `trust_manifest`. Same
tool call — richer result.

Ask the agent explicitly to discover via the ARD path:

```run
docker exec -i strands-agent python /app/agent.py <<< \
  "Use the ARD catalog to list every agent this federation publishes, and for each show its trust_manifest.identity + attestation types."
```

Watch the tool call. Your terminal shows dns-aid's full structlog
debug trace — one line per catalog fetch and card dereference. The
important lines (simplified):

```
  [tool]  discover_agents_via_dns({'use_http_index': True, 'domain': '<slug>.lab.ccdesanity.com'})
  [info]  catalog_pointer.resolved  label=_catalog._agents  url=…/.well-known/ai-catalog.json
  [info]  http_index.ard_catalog_detected  entry_count=8  spec_version=1.0
  [debug] Cap document fetched successfully  cap_uri=…/ip-reputation/mcp-server-card.json  capabilities_count=0
  [debug] ard_card.applied  agent=ip-reputation  protocol=mcp  source=ard_card
  … (×8 agents) …
  [info]  Discovery complete  agents_found=8  use_http_index=True
```

Then the agent answers **in natural language**. It's a Vertex Gemini
model, so the exact wording and layout vary run to run — what's
guaranteed is the content: 8 agents, each with its SPIFFE identity
and its 4 attestations, all pulled from the ARD catalog's
`trust_manifest`. A representative answer:

```
agent> The catalog lists 8 agents. Here are their identities and attestations:

- spiffe://lab.ccdesanity.com/agents/asn-info:       publisher-identity, SOC2-Type2, ISO27001-2022, GDPR-DPA
- spiffe://lab.ccdesanity.com/agents/cve-lookup:     publisher-identity, SOC2-Type2, ISO27001-2022, GDPR-DPA
- spiffe://lab.ccdesanity.com/agents/ip-reputation:  publisher-identity, SOC2-Type2, ISO27001-2022, GDPR-DPA
  … (5 more) …
```

> **You'll see `ard_card.applied source=ard_card` in the debug, yet
> the tool result tags `endpoint_source="http_index_fallback"` — why?**
> Two different things. `ard_card.applied` means dns-aid *dereferenced*
> each entry's `mcp-server-card.json` and applied it. But these 8
> agents are **catalog-only** (no authoritative per-agent DNS SVCB)
> and their reference cards are metadata-only (`capabilities_count=0`,
> no service URL). So the capability came from the card
> (`capability_source=agent_card`), but there was no real endpoint to
> bind — dns-aid fell back to the catalog-derived host
> (`endpoint_source=http_index_fallback`). You'd get
> `endpoint_source=ard_card` only if a card advertised a concrete,
> reachable endpoint. The `trust_manifest` — SPIFFE identity + 4
> attestations — is the real win here, and it came through the ARD
> path complete.

> **Same MCP tool, different transport.** The agent never learned a
> new function call. It set one flag (`use_http_index=True`), and
> dns-aid handled the entire ARD path — SVCB pointer resolution,
> catalog fetch, card dereferencing, trust-manifest surfacing. That's
> the pedagogical point: **discovery format changes don't propagate
> to the agent code**.

### The manual view — same catalog, direct curl

For comparison, hit the ARD Lambda directly (bypassing the MCP tool)
and see the raw catalog structure:

```run
echo "=== ARD federation catalog ==="
curl -s "${ARD_GLOBAL_CATALOG}" > /tmp/ard-response.json
python3 <<'PY'
import json
d = json.load(open("/tmp/ard-response.json"))
print(f"{len(d['entries'])} agents published by {d['host']['displayName']}")
PY

echo
echo "=== POST /search 'check if IP address is malicious' ==="
curl -s -X POST "${ARD_API_BASE}/search" \
    -H 'content-type: application/json' \
    -d '{"query":{"text":"check if IP address is malicious"}}' > /tmp/ard-response.json
python3 <<'PY'
import json
d = json.load(open("/tmp/ard-response.json"))
print(f"matched: {d['totalCount']} agents (ranked by token-overlap score)")
for r in d['results'][:3]:
    print(f"\n  score={r['score']:5.1f}  {r['displayName']}")
    print(f"    identifier    : {r['identifier']}")
    print(f"    version       : {r['version']}")
    print(f"    publisher     : {r['publisher']['identifier']}")
    print(f"    trust identity: {r['trustManifest']['identity']}")
    print(f"    cap_uri       : {r['metadata']['io.dnsaid.capUri']}")
    print(f"    policy_uri    : {r['metadata']['io.dnsaid.policyUri']}")
    print(f"    attestations  : {[a['type'] for a in r['trustManifest']['attestations']]}")
PY
```

The top result's `metadata."io.dnsaid.capUri"` and
`metadata."io.dnsaid.policyUri"` are **the same URLs** the DNS-AID
SVCB record's TXT companions carry. Different discovery transport →
same downstream artifacts → same backend invocation. ARD is a
**discovery substrate choice**, not a runtime-architecture choice.

> **Why this matters for federation interop**: an enterprise can run
> BOTH planes in parallel. DNS-aware clients (mobile, CLI tools,
> network appliances) use the SVCB path. Web-and-LLM-native clients
> (dashboards, registry browsers, agent search) use the ARD HTTPS
> path. The agent itself doesn't care — once it has the cap_uri it
> goes the same place. dns-aid-core 0.26+ will read ARD catalogs
> natively via the same `discover_agents_via_http_index` MCP tool
> path — until then, this lab demonstrates the transport via direct
> curl.

Try YOUR per-student federation view — same content, your URN
namespace:

```run
curl -s -X POST "${ARD_API_BASE}/students/${SANDBOX_SLUG}/search" \
    -H 'content-type: application/json' \
    -d '{"query":{"text":"ip reputation"}}' > /tmp/ard-response.json
python3 <<'PY'
import json
d = json.load(open("/tmp/ard-response.json"))
print(f"YOUR catalog matched: {d['totalCount']} agents")
top = d['results'][0]
print(f"top: {top['identifier']}")
print(f"     publisher  = {top['publisher']['identifier']}")
print(f"     trust id   = {top['trustManifest']['identity']}")
PY
```

Try a structured filter on the nested `trustManifest.attestations.type`
field path (ARD §7.1 dot-resolution):

```run
curl -s -X POST "${ARD_API_BASE}/search" \
    -H 'content-type: application/json' \
    -d '{"query":{"text":"intel","filter":{"trustManifest.attestations.type":["SOC2-Type2"]}}}' > /tmp/ard-response.json
python3 <<'PY'
import json
d = json.load(open("/tmp/ard-response.json"))
print(f"{d['totalCount']} threat-intel agents with SOC2-Type2 attestation:")
for r in d['results']:
    print(f"  {r['displayName']:20}  ({r['identifier']})")
PY
```

## Bonus 3 (optional) — watch the SDK caller-side guard deny a call

> Skip this section if you're short on time. It shows what the
> [dns-aid SDK](https://github.com/infobloxopen/dns-aid-core/tree/main/src/dns_aid/sdk/policy)
> caller-side guard does **before** an invocation ever leaves the
> agent process. Doesn't replace agentgateway enforcement — it adds
> a *first* layer that catches obvious policy violations without a
> network round-trip.

### What's already happening (default policy)

Every time the agent in this lab invokes `lookup_ip`, the SDK guard
runs against the policy at `${CAP_BASE_URL}/ip-reputation/policy.json`.
That policy whitelists `lookup_ip` via a CEL rule, so the call passes
through silently. You can see the guard line in the agent terminal:

```
  [sdk-guard] tool='lookup_ip' → ALLOWED by SDK caller guard
```

### Override to a STRICT policy that denies lookup_ip

A second policy doc lives next to the default at
`${CAP_BASE_URL}/ip-reputation/policy-strict.json`. Its CEL rule
**denies every tool call** (only `initialize` / `tools/list` allowed).
Point the agent at that one via the `POLICY_OVERRIDE` env, then ask
the same question:

```run
docker exec -i -e POLICY_OVERRIDE=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy-strict.json strands-agent python /app/agent.py <<< "Is 185.220.101.45 malicious?"
```

Expected — the SDK guard fires, the network call is **never made**,
and the model's reply surfaces the denial reason. Actual output from
the lab:

```
analyst>  [tool] discover_agents_via_dns({...})
[info     ] Discovery complete             agents_found=1 time_ms=51.94
  [dnssec]   ip-reputation.<slug>.lab.ccdesanity.com → ad
  [result] {"__cap_uri": "...v1.json", "__cap_doc": {...}}

  [tool] call_agent_tool({'tool_name': 'lookup_ip', 'arguments': {'ip': '185.220.101.45'}, ...})
2026-05-26 09:46:18 [debug ] policy.cel_backend             backend=rust
2026-05-26 09:46:18 [warning] mcp.policy_denied              method=tools/call mode=permissive
                                                              policy_uri=...policy-strict.json
                                                              protocol=mcp tool_name=lookup_ip
                                                              violations=["cel:tool-deny-all:STRICT policy:
                                                                          'lookup_ip' is BLOCKED.
                                                                          Only initialize/tools/list permitted."]
  [sdk-guard] tool='lookup_ip' → DENIED: cel:tool-deny-all: STRICT policy: 'lookup_ip' is BLOCKED. Only initialize/tools/list permitted.
  [result] {
    "success": false,
    "blocked_by": "dns-aid SDK caller-side guard (Layer 1)",
    "reason": "cel:tool-deny-all: STRICT policy: 'lookup_ip' is BLOCKED. Only initialize/tools/list permitted.",
    "policy_uri": "https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy-strict.json",
    "violations": [
      {
        "rule": "cel:tool-deny-all",
        "detail": "STRICT policy: 'lookup_ip' is BLOCKED. Only initialize/tools/list permitted."
      }
    ],
    "telemetry": {"latency_ms": 0, "status": "policy_denied"}
  }

agent> The lookup for 185.220.101.45 was blocked by a security policy.
       I cannot provide a verdict.

       **Reason:** The tool call was denied by the agent's security policy.
       The policy URI is `https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy-strict.json`,
       and the reason given was: "STRICT policy: 'lookup_ip' is BLOCKED. Only initialize/tools/list permitted."
```

**Notice five things in that output:**
- `mcp.policy_denied` is a **structured event from the official dns-aid
  SDK** (`dns_aid.sdk.policy.guard`) — same telemetry the dns-aid MCP
  server emits in production.
- `backend=rust` — the CEL rule is being evaluated by the SDK's
  high-performance Rust CEL backend (enabled by the `cel` extra).
- `telemetry.latency_ms = 0` — the call never left the agent process.
  The SDK guard refused before any network request.
- `violations[]` is a structured list of `{rule, detail}` — the agent's
  audit log gets exactly which CEL rule fired and why, not just a
  string. This is the same shape the target-side ASGI middleware would
  emit if the call had reached the server.
- The model receives the structured reason and *gracefully* refuses
  with a clean explanation — it doesn't retry forever, it doesn't
  hallucinate a verdict, it doesn't pretend the policy isn't there.

### Why this matters — four independent enforcement layers, one policy

DNS-AID's design is that the same `policy_uri` published in DNS is
evaluated at multiple, independent points. All four read the **same
policy document**; a deny at any layer blocks the request.

| Layer | Where | What it does | Exercised in this lab? |
|---|---|---|---|
| **Layer 0 — DNS resolver (bind-aid)** | resolver itself, via RPZ rules compiled from the policy | Resolver refuses to even tell a non-permitted caller where the target lives. Uses primitives our policy compiler emits to BIND-AID zone files. | ❌ — IETF2 workshop demos this with a bind9 + bind-aid integration |
| **Layer 1 — caller SDK** | inside the agent process | Refused to call a tool the published policy denies — *before* any network packet leaves. | ✅ — you just saw it |
| **Layer 2 — target SDK** | inside the agent SERVER (ASGI middleware) | Mandatory layer: even if a caller skipped the guard or lied about identity, the target re-checks and denies. | ❌ — same `PolicyEvaluator` runs as ASGI middleware; not wired here to keep the lab focused on caller-side |
| **Layer 3 — runtime sidecar (agentgateway)** | independent proxy in front of the target | Operates without trusting the caller's SDK. We use it here for routing/CORS; policy CEL on the gateway is an IETF2 add. | ☑ Partial — gateway runs but doesn't enforce policy yet |

Each layer is independently developed and operated. Layer 0 is the
resolver team, Layer 1 the AI-agent developer, Layer 2 the agent
publisher, Layer 3 the platform team. **One document drives them all.**

### Read the SDK code that did the work

The agent calls the **official dns-aid SDK helper** — no custom
wrapper. The helper lives at
[`dns_aid.sdk.policy.guard.check_target_policy`](https://github.com/infobloxopen/dns-aid-core/blob/main/src/dns_aid/sdk/policy/guard.py)
(shipped in `dns-aid>=0.21.3`) and is the same code path the
dns-aid MCP server itself uses for caller-side enforcement. Key call:

```python
from dns_aid.sdk.policy.guard import check_target_policy

result = await check_target_policy(
    policy_uri,                 # from cap doc / SVCB key65403
    tool_name=requested_tool,   # what your agent wants to call
    method="tools/call",
    caller_id="my-agent",
)
if result.denied:
    # Don't make the call. Surface result.reason / result.violations to your audit log.
    return refuse(result.reason)
```

In this lab the helper is wrapped in a single named function
**`sdk_policy_check()`** inside
[`agent_vertex.py`](https://github.com/iracic82/IETF_Vienna/blob/main/IETF-ARD/sandbox/strands-agent/agent_vertex.py)
— grep for it (`grep -n sdk_policy_check agent_vertex.py`) and you'll
see the entire integration in ~10 lines:

```python
async def sdk_policy_check(tool_name: str | None) -> PolicyResult:
    """Caller-side Layer 1 policy check via the official dns-aid SDK helper."""
    return await check_target_policy(
        policy_uri=_LAST_POLICY_URI,         # populated by DNS discovery
        tool_name=tool_name,                 # what Gemini wants to call
        method="tools/call",
        caller_id="strands-agent-ietf-lab",
    )
```

Called from the tool-dispatch loop right before each `call_agent_tool`:

```python
if name == "call_agent_tool":
    sdk_decision = await sdk_policy_check(args.get("tool_name"))
    if sdk_decision.denied:
        # synthesise denial JSON, skip the network call
        return _make_denial_response(sdk_decision)
```

That's it. No custom wrapper, no policy parsing in agent code —
everything else is the SDK's job.

Behind the scenes the helper:

1. Fetches the target's `policy_uri` over HTTPS (URL-safety checks built-in).
2. Caches the parsed `PolicyDocument` (TTL via `DNS_AID_POLICY_CACHE_TTL`, default 300s).
3. Builds a `PolicyContext` from your request (method, tool_name, protocol, caller_id, …).
4. Runs `PolicyEvaluator().evaluate(...)` at `PolicyEnforcementLayer.CALLER`.
5. Returns a `PolicyResult` with `.allowed`, `.denied`, `.reason`, `.violations`.

Operational knobs:

| Env var | Effect |
|---|---|
| `DNS_AID_POLICY_MODE=disabled` | Helper short-circuits to `allowed=True` (kill-switch for incidents) |
| `DNS_AID_POLICY_CACHE_TTL=N` | Cache parsed policy docs for N seconds (default 300) |
| `DNS_AID_CALLER_DOMAIN=...` | Adds the caller's domain to `PolicyContext.caller_domain` for domain-scoped rules |

Fail-open semantics on network/parse errors — sensible default for
production. Override by wrapping the call yourself if you want
hard-failure behaviour.

### Restore the default

The `POLICY_OVERRIDE` env was set per `docker exec` invocation, so the
next agent run (without `-e POLICY_OVERRIDE`) goes back to the
permissive default — no cleanup needed.

## The DAWN argument, in one paragraph

You just watched an AI agent **discover** a capability via standards-based
DNS (no hardcoded endpoint, no central registry), **verify** its
authenticity (DNSSEC chain to root + cryptographic cap doc), **gate**
the invocation via the SDK caller-side policy guard, and **invoke**
through a runtime enforcement layer (agentgateway, xDS-driven routes).
The agent never knew the endpoint before the question was asked. It
only knew the naming convention. **Discovery, identity, and policy
are separate layers — governed at different times, by different teams,
using protocols that already exist.** That's the DAWN argument made
literal.

## Success

Auto-completes after at least one successful `lookup_ip` tool call
through the federation.
