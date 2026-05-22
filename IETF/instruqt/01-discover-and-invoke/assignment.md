---
slug: discover-and-invoke
id: mpmqykxvsmtx
type: challenge
title: 1. Tour the lab
teaser: Read the Strands agent code and explore the running stack — before publishing
  anything.
notes:
- type: text
  contents: |-
    The lab stack is starting up — agentgateway, fastmcp-ip-reputation,
    coredns, the visualizer, and the Strands agent (with `dns-aid`
    pre-installed). DNS records are NOT yet published — that's the next
    challenge.

    Take a tour first. Open the **Editor** tab, then explore.
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
- id: dkrksnqefjtn
  title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 600
enhanced_loading: null
---

# 1. Tour the lab

## What's running

In the **Terminal** tab:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

You should see 7 containers — coredns, event-hub, fastmcp-ip-reputation, agentgateway, dns-aid-mcp, strands-agent, viz.

## Read the agent code

In the **Editor** tab, navigate to `lab/IETF/sandbox/strands-agent/`:

- `agent.py` — the REPL that drives the Strands agent
- `Dockerfile` — what's installed (Strands + LiteLLM Vertex + dns-aid + mcp)

Then `lab/shared/strands_dnsaid/`:

- `factory.py` — how the agent is built (model + tools)
- `prompts.py` — the system prompt that tells the agent *how* to use DNS-AID

Spend 2 minutes reading. The agent doesn't know any endpoint. It only knows the naming convention `_<name>._<proto>._agents.<domain>` — it discovers via DNS at runtime.

## Look at the gateway

Open the **agentgateway UI** tab. Click through binds → listeners → routes → backends. Path mode: `/ip-reputation/mcp` routes to `fastmcp-ip-reputation:3000`.

## Check DNS state — should be empty

```bash
source /tmp/sandbox.env
echo "subdomain = ${SANDBOX_SLUG}.${ZONE}"

dig +short SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
# (no output expected — nothing published yet)
```

## When you're ready

Move to the next challenge — you'll publish your federation's first capability via the `dns-aid` CLI.

## Success

Auto-completes when all 7 lab containers are healthy.
