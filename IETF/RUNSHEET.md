# IETF Vienna — DNS-AID Stage Demo Runsheet

12 minutes. 5 scenes. Two screens: terminal (Strands agent) + browser
(DNS-AID Explorer visualizer). Sandbox is already running.

## Pre-flight (run 10 min before talk)

- [ ] Instruqt sandbox running, terminal shows the assistant prompt
- [ ] DNS-AID Explorer loaded in second browser, "Live mode" toggled
- [ ] Backup: pre-recorded MP4 of the same flow on hotkey F9
- [ ] Test query in private: confirm `185.220.101.45` returns malicious

## Scene 1 — Set the problem (2 min)

**Slide 1 — "An AI agent needs a capability it doesn't have."**

Say:
> "Most AI agent demos hand you a system with every tool pre-wired. The
> real problem is the *discovery problem*: how does an agent find a
> capability it didn't ship with, from another organization, without a
> central registry, with verifiable trust?
>
> Today's answer: DNS. Same DNS your laptop uses to find Wikipedia is
> the answer to how AI agents find each other."

**Slide 2 — DNS-AID record shape:**
```
_ip-reputation._mcp._agents.<domain>  SVCB 1 gw.<domain>.
                                              alpn="mcp,h2"
                                              key65400="...cap.json"
                                              key65401="<cap-sha256>"
```

> "One SVCB record. Standard DNS. Add DNSSEC and you've got authenticated
> discovery. That's the IETF draft we're discussing this week."

## Scene 2 — Show the world (2 min)

Switch to **terminal**. Run:

```bash
$ dig +dnssec SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.workshop.highvelocitynetworking.com
```

Point at the **AD flag** in the output.

> "AD = Authenticated Data. The chain-of-trust from root to this record
> validated. That's free, that's DNSSEC. Nothing AI-specific. Nothing
> new."

Then:

```bash
$ curl https://gw.${SANDBOX_SLUG}.workshop.highvelocitynetworking.com/ip-reputation/cap.json | head
```

> "Capability document. JWS-signed. Tells the caller what tools this
> agent exposes, what auth it needs, what its policy URI is."

## Scene 3 — Watch the agent do it (4 min)

Switch to **DNS-AID Explorer**. Make sure it's on Step 1.

Switch to **terminal**:

```
analyst> Is 185.220.101.45 malicious?
```

As the agent runs, point at the visualizer. Each step lights up:

| Step | Visualizer node | What to call out |
|---|---|---|
| 1 | Strands ◯ | "Agent picks the discover tool. No hard-coded endpoint." |
| 2 | dns-aid MCP ◯ | "Tool call goes to the dns-aid library — a thin wrapper around real DNS." |
| 3 | CoreDNS ◯ | "Local resolver, DNSSEC-validating." |
| 4 | Route 53 ◯ | "Auth zone. Signed once. Updated by `dns-aid publish`." |
| 5 | Cap doc store ◯ | "Gateway serves the cap doc. Sha256 in the SVCB record matches." |
| 6 | JWKS ◯ | "JWS signature on the cap doc verified — signer is `k-ops-team-2026`." |
| 7 | agentgateway ◯ | "Mandatory hop. Routes by URL path. Policy enforcement layer." |
| 8 | FastMCP ip-reputation ◯ | "Actual lookup. Real verdict from real data." |
| 9 | response | "Verdict + audit trail. The trust chain is visible to the analyst." |

Verdict appears:
```
agent> 185.220.101.45: MALICIOUS (confidence 0.95)
       sources: tor-exit-list, abuse.ch  tags: tor
       audit:   discovered via SVCB at _ip-reputation._mcp._agents.${SLUG}...
                DNSSEC: AD flag verified
                cap-doc: JWS signed by k-ops-team-2026
                invoked via: gw.${SLUG}.workshop.highvelocitynetworking.com
                routed by: agentgateway
```

## Scene 4 — Drive the point home (2 min)

Say:
> "Two things just happened that you might miss. First — *I never told
> the agent where to look.* It only knew the federation's naming
> convention. Second — *the trust chain is end-to-end made of standards*.
> DNSSEC for the record. JWS for the cap doc. TLS for the channel.
> Nothing new. Nothing proprietary. Nothing AI-specific.
>
> The agentgateway in the middle is the *runtime* enforcement layer —
> separate from the discovery layer. That separation is the DAWN
> argument: discovery and invocation are different concerns, governed at
> different layers, by different teams."

Switch to **DAWN-MAPPING.md** on screen. Walk the ✅ rows quickly.

## Scene 5 — Honest gaps + next (2 min)

Stay on **DAWN-MAPPING.md**. Read the ⚠️ rows.

> "Things this demo *doesn't* cover, on purpose: resolution-layer
> enforcement, blast-radius investigation, key revocation. They're in
> the companion 90-minute workshop — same federation, but you walk
> through an incident response triggered by a terminated employee whose
> JWKS key wasn't revoked in time. QR code's on the slide."

Show QR → DNS-AID Workshop track in Instruqt.

> "Questions?"

## If things break

| Symptom | Fix |
|---|---|
| Agent hangs | Hit Ctrl-C in terminal, try again. Vertex AI sometimes slow. |
| Visualizer doesn't update | Refresh browser tab; SSE reconnects on its own. |
| `dig` returns SERVFAIL | Falling back to public resolver: `dig @1.1.1.1 ...` |
| Total disaster | F9 → backup MP4 plays. Narrate over it. |
