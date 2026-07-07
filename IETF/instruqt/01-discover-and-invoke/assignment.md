---
slug: discover-and-invoke
id: mpmqykxvsmtx
type: challenge
title: 1. Tour the lab
teaser: Inspect a federation runtime that has zero routes until DNS publishes one.
  Then watch how it discovers.
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
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# 1. Tour the lab — DNS as the control plane

## The setup

You are a SOC analyst at a security org that participates in a
federated threat-intelligence network. Other organisations publish
capabilities (IP reputation, URL scanning, CVE lookup, passive DNS, …)
into shared DNS zones. Your AI assistant has to **find** those
capabilities, **trust** them, and **invoke** them — without anyone
hand-coding endpoint URLs.

DNS-AID is the IETF draft + reference implementation that makes this work:

- IETF draft: [`draft-mozleywilliams-dnsop-dnsaid`](https://datatracker.ietf.org/doc/draft-mozleywilliams-dnsop-dnsaid/)
- Project site: [dns-aid.org](https://dns-aid.org)
- Reference implementation: [`dns-aid/dns-aid-core`](https://github.com/dns-aid/dns-aid-core)
  — Python library, CLI, MCP server, and an SDK with **caller- and
  target-side policy enforcement** (the part this lab exercises).

## What's different about this lab vs. a typical "agent calls agent" demo

| Conventional setup | DNS-AID federation (this lab) |
|---|---|
| Endpoints hard-coded in client config or vendor registry | Endpoints **discovered at runtime via DNS** — SVCB record under `<name>.<zone>` |
| Trust = "we both have the same API key" | **Layered trust signals**: DNSSEC for record integrity → DANE/TLSA for cert binding → JWS signature on cap doc → JWKS for key publication |
| Capability metadata in a vendor SDK | **Cap document** (JSON, published independently): tools, schemas, version, `policy_uri`, `cap_sha256` |
| Policy = "the client behaves" | **Policy enforced at multiple independent layers** (see below) |
| Adding a new capability = ticket → CI → deploy | **Adding a capability is a DNS publish.** Removing = DNS delete. No code change, no gateway restart. |

## Where policy gets enforced

DNS-AID's design is that the same `policy_uri` published in DNS is
evaluated at multiple, independent points. This lab exercises the
**two SDK enforcement points** in the [`dns_aid.sdk.policy`](https://github.com/dns-aid/dns-aid-core/tree/main/src/dns_aid/sdk/policy)
package:

1. **Caller-side guard** — before the agent invokes a discovered
   capability, the SDK fetches the target's `policy_uri` from DNS,
   evaluates it (allowed methods, rate limits, CEL expressions),
   and **refuses to make the call** if it violates the contract.
2. **Target-side ASGI middleware** — the agent SERVER exposes its
   capability through middleware that re-evaluates the same policy
   on every incoming request and **rejects** anything non-compliant.
   This is the *mandatory* layer: regardless of whether the caller
   SDK cooperated, the target re-checks and denies.

On top of those two, this lab also runs a **runtime sidecar gateway**
(agentgateway) in front of the target. It's an independent enforcement
surface — request routing, CORS, future authn/authz, observability —
that operates without trusting the caller's SDK behaviour.

> **Out of scope for this lab — mentioned for context:**
> DNS-AID also supports compiling a policy down to **Response Policy
> Zone (RPZ)** directives that a DNSSEC-aware resolver (e.g. BIND with
> [bind-aid](https://github.com/dns-aid/dns-aid-core/tree/main/docs)
> integration) can enforce — meaning the resolver itself refuses to
> even tell a non-permitted caller where the target lives. We don't
> demo the resolver layer here; that's the IETF2 workshop.

## The xDS twist — gateway routes come from DNS, in real time

The agentgateway in this lab has **zero static routes** at boot.
A separate container — the *xDS translator* — polls Route 53 every
5 seconds. When a SVCB record appears under your sandbox subdomain,
the translator encodes a `Bind` + `Listener` + `Route` + `Backend`
as Envoy v3 ADS resources and pushes them to agentgateway over a
continuously-open gRPC Delta stream. When the record disappears,
the route disappears.

So: **DNS is the runtime control plane** — for both the agent's
discovery and the gateway's route table. One mental model — "publish
to DNS → it exists; delete from DNS → it's gone" — applies to both
planes simultaneously.

## What's running

Open **Terminal** and run:

```run
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
Two ways to confirm:

**Way 1 — agentgateway UI tab.** Open it. You'll see:

- A purple banner at the top that says:
  > *"Configuration is managed by an external source (XDS). Editing the
  > configuration is not allowed via the UI."*

  **Read that banner carefully.** That's the gateway literally
  telling you it doesn't own its routes — they come from xDS. No human
  edits this UI. The translator pushes everything.

- Sidebar counters: **Listeners 1**, **Routes 0**, **Backends 0**.

  (Routes/backends will tick to 1 in Challenge 2 the moment you publish.)

**Way 2 — terminal.**

```run
# Try to invoke ip-reputation directly — 404 because no route exists
curl -sw '%{http_code}\n' -o /dev/null \
    -X POST http://localhost:3000/ip-reputation/mcp \
    -H 'content-type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
# Expected: 404
```

This is the **before** state. In Challenge 2 you'll change it by
publishing one DNS record — and the UI's counters will tick up
automatically.

## Read the agent code

Open
[`IETF/sandbox/strands-agent/agent_vertex.py`](https://github.com/iracic82/IETF_Vienna/blob/main/IETF/sandbox/strands-agent/agent_vertex.py)
on GitHub, or click ▶ below to read it in the terminal (press `q` to quit `less`):

```run
less /opt/lab/IETF_Vienna/IETF/sandbox/strands-agent/agent_vertex.py
```

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

```run
source /opt/lab/lab.env
echo "your subdomain = ${SANDBOX_SLUG}.${ZONE}"
echo "DNSSEC chain   = root → .com → ccdesanity.com → ${ZONE} (validated)"

# Empty for now — no records published yet
dig +noall +answer SVCB ip-reputation.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
```

## Watch the translator

```run
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
