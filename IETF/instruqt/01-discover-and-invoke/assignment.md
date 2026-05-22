---
slug: discover-and-invoke
id: mpmqykxvsmtx
type: challenge
title: Discover and invoke a federation capability
teaser: An AI threat-intel assistant finds the right MCP server via DNS — then invokes
  it through the gateway.
notes:
- type: text
  contents: |-
    The federation publishes its capabilities as SVCB records under
    `_<name>._mcp._agents.<your-subdomain>.workshop.highvelocitynetworking.com`.

    You'll watch the AI assistant:
    1. Discover the `ip-reputation` capability via DNS-AID
    2. Verify DNSSEC (AD flag) + JWS signature on the cap document
    3. Open an MCP connection through agentgateway
    4. Return the verdict with a full audit trail
tabs:
- id: ypuacyuxwmjd
  title: Terminal
  type: terminal
  hostname: host
- id: 7twsmk4qgck5
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: 3pf6brlgo8ag
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
difficulty: basic
timelimit: 900
enhanced_loading: null
---

# Discover and invoke a federation capability

## The story

You're the on-call analyst at a SOC that joined the **Threat-Intel Federation** last week. Member organizations publish their capabilities via DNS-AID — an IETF draft for AI agent discovery using DNS records, DNSSEC, and JWS-signed capability documents.

Your AI assistant doesn't know what's in the federation. It just knows the federation's **predictable entry point**: agents live under `_<name>._mcp._agents.<your-subdomain>`.

## Your task

In the **Terminal** tab, the lab stack is already running. Talk to the Strands assistant:

```
docker exec -it strands-agent python /app/agent.py
```

Then ask it about a suspicious IP:

```
analyst> Is 185.220.101.45 malicious?
```

The assistant will discover the `ip-reputation` capability via DNS-AID, verify the discovery is authentic, and invoke it through **agentgateway** (the mandatory runtime enforcement hop — no direct agent-to-MCP calls).

Try a known-clean one too:

```
analyst> What about 8.8.8.8?
```

## What to watch

Open the **DNS-AID Explorer** tab. As the assistant runs, each protocol step lights up in the flow graph, with full request / response details in the side panel.

## DAWN requirements this demonstrates

- ✅ **Predictable entry point** — naming convention `_<name>._<proto>._agents.<domain>`
- ✅ **Decentralized publication** — each member runs `dns-aid publish` on their zone
- ✅ **Service metadata** — SVCB key65400 → cap doc; key65401 → content hash
- ✅ **Authenticated discovery** — DNSSEC AD flag + JWS signature on cap doc
- ✅ **Runtime enforcement** — agentgateway is the mandatory hop

## Verification

The challenge auto-completes when you've made at least one successful `lookup_ip` invocation that returned a non-error verdict.
