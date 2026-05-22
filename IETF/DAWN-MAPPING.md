# DAWN Requirements — Coverage by the IETF Vienna Lab

Honest mapping of what this demo proves and what it doesn't.
Companion `IETF2/` lab covers the orange and red rows.

## ✅ Demonstrated end-to-end

| DAWN requirement | Mechanism | Where in the demo |
|---|---|---|
| Predictable discovery entry point | DNS naming convention `_<name>._<proto>._agents.<domain>` | Scene 2 — `dig` against the SVCB record |
| Decentralized publication | Each member runs `dns-aid publish` against their own zone | Pre-recorded (publication happened on bootstrap) |
| Service / capability metadata | SVCB record (target, port, alpn) + cap doc (tools, schemas, policy) | Scene 2 — `dig` + `curl` of `cap.json` |
| Authenticated discovery (record integrity) | DNSSEC chain-of-trust + `AD` flag verification | Scene 2 + Scene 3 step 3 |
| Capability attestation (claim integrity) | JWS-signed cap doc; JWKS at `.well-known/jwks.json` | Scene 3 step 6 |
| Stable identity through backend churn | Cap-sha256 in SVCB key65401 unchanged when backend restarts | "No-churn" property — slide mention, demo'd in IETF2 workshop |
| Runtime enforcement / invocation policy | agentgateway is mandatory; no direct agent-to-MCP calls | Scene 3 step 7 — gateway routes by URL path |
| Protocol agnosticism | Same DNS shape for MCP, A2A, plain HTTPS | Slide mention; demonstrated by record naming |

## ⚠️ Partially demonstrated (covered in IETF2 workshop)

| DAWN requirement | Mechanism | Gap explanation |
|---|---|---|
| Resolution-layer enforcement | RPZ in local recursive resolver | IETF lab has the resolver but doesn't push any RPZ rules; IETF2 challenge 2 walks through containment |
| Discovery-layer revocation | `dns-aid delete_agent_from_dns` + RPZ block on signer key | IETF2 challenge 3 |
| Defense in depth across layers | Resolution (RPZ) + Discovery (DNSSEC/JWS) + Invocation (gateway policy) | IETF lab shows two of three; IETF2 shows all three working together |

## ❌ Not demonstrated in this scope

| DAWN requirement | Why omitted / where it goes |
|---|---|
| Telemetry feedback to a directory | Possible via dns-aid Tier-1 SDK; out of scope for both labs (would add Tier-1 directory infrastructure) |
| Cross-protocol federation (MCP + A2A in one query) | Future work — cleanly modeled by DNS-AID schema; demo intentionally single-protocol for clarity |
| Cross-domain federation (multiple zones, multiple trust roots) | Future work — IETF 126 candidate |
| Capability composition / planning across agents | Out of scope; this is an agent-runtime concern (Strands handles it locally), not a discovery concern |

## Why these gaps are not red flags

The IETF Vienna lab is a **focused, 15-minute demo of the discovery
primitive**. We intentionally narrowed scope to make the protocol work
unambiguously visible. Every "missing" item above is either:

1. Architecturally trivial given what's demonstrated (e.g. cross-protocol
   is just a different `_<proto>._agents.` label),
2. Demonstrated in the companion IETF2 workshop (resolution enforcement,
   blast radius, hardening),
3. Or genuinely future work for the IETF community (multi-trust-root
   federation, planning-layer concerns).

Resisting feature creep here is what makes the demo land. The discovery
primitive is the IETF-relevant artifact; everything else is application
on top.
