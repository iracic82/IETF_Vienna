# IETF Vienna — DNS-AID Labs

Two Instruqt labs demonstrating DNS-AID (DNS-based AI agent identification and
discovery) as a discovery primitive for AI agent ecosystems, with
[agentgateway](https://agentgateway.dev) as the mandatory runtime enforcement
layer.

Both labs share a polished web visualizer — **DNS-AID Explorer** — that
animates the discovery flow in real time.

## The two labs

| | **IETF** | **IETF2** |
|---|---|---|
| Audience | IETF Vienna attendees (protocol designers) | Sec-ops practitioners |
| Length | 12–15 min | 60–90 min |
| Story | Discover and invoke a remote MCP capability via DNS-AID | Live through an AI-supply-chain incident response |
| Challenges | 1 | 4 |
| Sandbox shape | 6 containers | 13 containers |

## Scenario — Threat Intel Federation

A coalition of organizations publishes threat-intelligence agents via DNS-AID.
An AI SOC analyst's assistant discovers what's available in the federation,
verifies signed metadata, and invokes capabilities through the gateway.

Capabilities (all reuse the same `fastmcp-template` Docker image, configured
by env vars):

- `ip-reputation` — verdict on an IP (clean / malicious / unknown)
- `url-scanner` — phishing / malware verdict for a URL
- `file-hash` — known-bad / known-good for SHA-256
- `cve-lookup` — severity + affected products by CVE ID
- `domain-age` — first-seen + registrar
- `asn-info` — ASN + country + ISP for an IP
- `passive-dns` — historical resolutions for a name

IETF lab uses one (`ip-reputation`). IETF2 uses all seven plus a rogue
`threat-feed` agent and a tampered variant of `ip-reputation` (Challenge 3
blast-radius reveal).

## Architecture (per sandbox)

```
Instruqt sandbox = 1 GCP project + 1 GCE VM
├── coredns          local recursive resolver + per-sandbox RPZ
├── strands-agent    Strands + LiteLLM(vertex_ai/claude-sonnet-4)
├── dns-aid-mcp      python -m dns_aid.mcp.server
├── agentgateway     mandatory runtime hop; path-mode routing
├── fastmcp-agents/  threat-intel capability servers
├── sidecars/        event emission for the visualizer
└── viz              DNS-AID Explorer (Next.js + shadcn + React Flow)

External (shared):
└── Route 53: workshop.highvelocitynetworking.com (DNSSEC signed)
```

Each sandbox gets a unique `SANDBOX_SLUG` (8-char hex) from Instruqt's
`random_id` resource, used to template all per-sandbox DNS names:
`gw.${SLUG}.workshop.highvelocitynetworking.com`,
`_<agent>._mcp._agents.${SLUG}.workshop.highvelocitynetworking.com`, etc.

## Layout

```
IETF_Vienna/
├── shared/                  reused across both labs
│   ├── fastmcp-template/    one image, all 7 capabilities
│   ├── agentgateway/        path-mode config + cap docs
│   ├── strands_dnsaid/      Strands wiring to dns-aid MCP
│   ├── trust/               JWKS key pairs + JWS helpers
│   ├── dns-seed/            Route 53 zone generator
│   ├── coredns/             Corefile template + RPZ seed
│   └── sidecars/            event emission for the visualizer
├── IETF/                    short focused track
├── IETF2/                   full 4-challenge workshop
└── viz/                     DNS-AID Explorer web app
```

## Tech stack

| Layer | Choice |
|---|---|
| Agent runtime | Strands Agents |
| Model | Claude Sonnet 4.6 via Vertex AI (LiteLLM provider) |
| Discovery | dns-aid MCP server (Python) |
| Gateway | agentgateway (path-mode routing) |
| Capability servers | FastMCP (one Dockerfile, 7 agents via env vars) |
| Resolver | CoreDNS (recursive + RPZ) |
| Auth DNS | Route 53 (DNSSEC at parent zone) |
| Sandbox compute | GCE e2-standard-2 per learner |
| Visualizer | Next.js 16 + shadcn/ui new-york + React Flow 12 |

## Cost estimate

| Lab | Per learner | 30 learners |
|---|---|---|
| IETF (~15 min) | ~$0.12 | ~$3.60 |
| IETF2 (~90 min) | ~$0.40 | ~$12.00 |

Route 53 hosted zone: marginal.

## See also

- `IETF/RUNSHEET.md` — Vienna stage demo speaker notes
- `IETF/DAWN-MAPPING.md` — DAWN requirements coverage table
- `IETF2/PRESENTER-GUIDE.md` — workshop facilitator notes
- `viz/README.md` — DNS-AID Explorer development guide
