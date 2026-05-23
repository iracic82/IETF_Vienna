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

## Look at the agentgateway UI

Open **agentgateway UI** tab. Navigate to Routes → `ip-reputation-mcp`.
You'll see:

- Match: `/ip-reputation/mcp`
- Backend: `fastmcp-ip-reputation:3000`
- **Source: xDS (from translator)** — not from a static config file

This route exists because of a DNS record. Delete the record and within
5 seconds the route is gone (you can demo this — see C2's optional
section).

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
