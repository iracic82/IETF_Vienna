---
slug: discover-and-invoke
id: mpmqykxvsmtx
type: challenge
title: 1. Tour the lab — DNS as the control plane
teaser: Inspect a federation runtime that has zero routes until DNS publishes one. Then watch how it discovers.
notes:
- type: text
  contents: |-
    Welcome to the IETF Vienna DNS-AID demo. You're about to operate a
    threat-intel federation where DNS is the control plane — not a
    config file, not Kubernetes CRDs, not a registry. Just DNS.

    This first challenge is a tour. No publishing yet. Read the running
    stack, understand each piece, then move to the publish challenge.
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
timelimit: 1800
enhanced_loading: null
---

# 1. Tour the lab — DNS as the control plane

## The setup, in one paragraph

You are a SOC analyst at a security org that's part of a federated
threat-intel network. Other orgs publish capabilities into shared DNS
zones; your AI assistant discovers them at runtime via DNS-AID
([IETF I-D draft-mozleywilliams-dnsop-dnsaid](https://datatracker.ietf.org/doc/draft-mozleywilliams-dnsop-dnsaid/))
and calls them through a runtime enforcement layer (agentgateway).

What makes this different from "AI agent calls another AI agent"
demos:

- **Discovery is via DNS.** No registry, no SDK, no hardcoded endpoint.
  The agent only knows the naming convention `_<name>._<proto>._agents.<zone>`.
- **Runtime enforcement is mandatory.** Every invocation goes through
  agentgateway. Policy lives there, not in client code.
- **The gateway's routes come from DNS, not from a config file.**
  An xDS translator watches DNS and pushes routes into agentgateway in
  real time. Publish a record → route appears. Delete it → route disappears.

## What's running

Open **Terminal** and run:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

You should see 8 containers:

| Container | Role |
|---|---|
| `coredns` | Local DNS resolver (forwards upstream + serves any local overlays). Host port `5353`. |
| `event-hub` | Pub/sub bus for the visualizer. |
| `fastmcp-ip-reputation` | The actual MCP server. Exposes `lookup_ip` on `:3000/mcp`. Not externally addressable. |
| `translator` | **xDS translator.** Polls Route 53 every 5s for SVCB records under your sandbox zone, encodes discovered agents as Envoy v3 ADS resources, streams them to agentgateway. |
| `agentgateway` | Runtime enforcement layer. **Has zero routes at boot** — they materialize when DNS records appear. |
| `dns-aid-mcp` | Wraps the `dns-aid` CLI as an MCP server the AI agent can call. |
| `strands-agent` | The AI assistant (Vertex Gemini direct, MCP tools, REPL). |
| `viz` | DNS-AID Explorer visualizer (port 8080). |

## Prove the gateway is empty

Before any DNS publish exists, the gateway has nothing to route to.
Confirm:

```bash
# 1. Open the agentgateway UI tab → Routes panel → "0 routes"
#    Or via the admin API:
curl -s http://localhost:15000/api/routes 2>&1 | head -20

# 2. Try to invoke ip-reputation directly — 404
curl -sw '%{http_code}\n' -o /dev/null \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
# Expected: 404 (no route)
```

This is the **before** state. In challenge 2 you'll change it by
publishing one DNS record.

## Read the agent code

In the **Editor** tab, open `lab/IETF/sandbox/strands-agent/agent_vertex.py`.
Key bits:

- **`SYSTEM_PROMPT`** (top of file) — tells the model "never answer from
  training data, always query the federation via DNS-AID first."
- **`_enrich_with_cap_doc`** — after the model calls discover, the
  wrapper auto-fetches the S3 cap doc and the DNSSEC AD flag, then
  inlines both into the response. The model reads the actual contract
  before invoking. *This is the lab's honesty layer.*
- **`_canonical_endpoint`** — Gemini sometimes hallucinates URLs (e.g.
  `httpshttps://` or wrong hosts). The wrapper rewrites every tool-call
  endpoint to the canonical `http://agentgateway:3000/<agent>/mcp`.

Also worth a look:

- `lab/IETF/sandbox/docker-compose.yml` — see how `agentgateway` has
  `depends_on: [translator]` and **no static config except `xdsAddress`**.
  Routes come from the translator.
- `lab/shared/agentgateway/render-config.py` — emits the minimal
  xDS-only config the gateway needs.
- `lab/docs/caps/ip-reputation/{v1,mcp-server-card,policy}.json` — the
  published contract for ip-reputation. These files are hosted on a
  public S3 bucket; the DNS-AID record will point at them via
  `--cap-uri` / `--policy-uri` in challenge 2.

## Check public DNS state for your subdomain

```bash
source /opt/lab/lab.env
echo "your subdomain = ${SANDBOX_SLUG}.${ZONE}"
echo "DNSSEC chain   = root → .com → ccdesanity.com → ${ZONE} (validated)"

# Empty for now — no records published yet
dig +noall +answer SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
```

## Watch the translator

```bash
docker logs --tail 30 translator
```

You'll see it polling DNS every 5 seconds. Right now it sees nothing.
After challenge 2 it will see the record you published and push a
route to the gateway in real time.

## When you're ready

Move to challenge 2 — publish your federation capability and watch the
gateway materialize the route within seconds.

## Success

Auto-completes when all 8 containers are healthy.
