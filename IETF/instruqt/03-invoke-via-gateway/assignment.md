---
slug: invoke-via-gateway
type: challenge
title: 3. Invoke via the gateway
teaser: Watch the Strands agent discover your published capability and call it through agentgateway.
notes:
- type: text
  contents: |-
    The record you published in challenge 2 is now the federation's
    discovery anchor. Run the Strands agent and ask a question — it
    will discover, verify, and invoke ip-reputation entirely on its own.
tabs:
- title: Terminal
  type: terminal
  hostname: host
- title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- title: agentgateway UI
  type: service
  hostname: host
  port: 15000
- title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 600
enhanced_loading: null
---

# 3. Invoke via the gateway

## Start the agent

```bash
docker exec -it strands-agent python /app/agent.py
```

## Ask a question

```
analyst> Is 185.220.101.45 malicious?
```

Watch the **DNS-AID Explorer** tab as the agent runs. You'll see:

1. Strands selects `discover_agents_via_dns`
2. DNS query against your subdomain → SVCB returned (the one you published)
3. Gateway endpoint extracted + cap doc fetched
4. MCP `tools/call` for `lookup_ip` flows through agentgateway → fastmcp-ip-reputation
5. Verdict returned with full audit trail

## Try a known-clean IP

```
analyst> What about 8.8.8.8?
```

## Try the visualizer side-panel

In the DNS-AID Explorer, click a step in the flow graph. The right panel shows the actual request / response payload for that step.

## DAWN money shot

You just watched an AI agent:

- **Discover** a capability via standards-based DNS (no SDK, no registry)
- **Verify** authenticity (DNSSEC + JWS-signed cap doc)
- **Invoke** through a runtime enforcement layer (agentgateway)

The agent never knew the endpoint. It only knew the naming convention. That's the DAWN argument made literal.

## Success

Auto-completes after at least one successful `lookup_ip` tool call.
