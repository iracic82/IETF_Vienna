# IETF2 Workshop — Presenter Guide

90 minutes. 4 challenges. 20–30 participants. Each participant gets
their own Instruqt sandbox (separate GCP project, separate VM, separate
subdomain).

## Pre-workshop checklist (T-30 min)

- [ ] Verify Instruqt track is live, sandboxes spin up within ~3 min
- [ ] Check Route 53 zone has hosted zone ID exposed to sandbox via secret
- [ ] Spot-check one sandbox: `docker ps` shows 14 services healthy
- [ ] Test the DNS-AID Explorer loads
- [ ] Slack/Discord channel open for questions
- [ ] Co-facilitator on standby for stuck participants

## Opening (5 min)

**Slide 1 — "Imagine your AI SOC analyst has been compromised."**

Set the stakes:
> "Every AI assistant in your organization needs to know what tools and
> capabilities are available. Today most do that via SDKs, hardcoded
> URLs, or per-org registries. Each of those is also a *new attack
> surface*.
>
> In the next 90 minutes you'll walk through a real attack vector that's
> opened by AI-supply-chain trust assumptions — and you'll see how
> standards-based DNS infrastructure can mitigate it with zero new
> middleware."

**Slide 2 — The federation diagram + the email from HR.**

> "Read the email. That's where Challenge 1 starts. Open your Instruqt
> sandbox. The terminal is your AI SOC assistant. You drive."

## Per-challenge facilitation

### Challenge 1 — Something doesn't belong (20 min)

**What you want to hear from the room at the end:**
> "It's not the signature — the signature is technically valid because
> David's key wasn't revoked yet. It's the *combination* of signals:
> timestamp after termination + external endpoint + always-clean
> behavior + missing policy URI."

**Common stuck point #1:** "How do I know which agents are 'supposed' to
be there?"
**Nudge:** "Your assistant has a `list_agent_index` tool. Ask it. It'll
show you the directory's TXT record. Then compare to your runbook (the
one in the wiki / pretend wiki)."

**Common stuck point #2:** "verify_agent_dns says the signature is
valid — isn't that enough?"
**Nudge:** "Yes, *cryptographically*. Now ask the assistant when the
record was published. And what its endpoint is. And whether it has a
policy URI. Each signal alone is harmless. Together they're a tell."

### Challenge 2 — Contain (15 min)

**What to call out:**
> "Notice you didn't file a ticket. You didn't change a firewall. You
> didn't restart anything. The RPZ rule lives at your *resolver*, and
> it took effect immediately. This is the kind of containment a regular
> firewall change can't give you."

**Common stuck point:** "But the rogue backend is still running, isn't
it?"
**Answer:** "Yes — at the network layer. But no AI client in your
federation can find it anymore. That's the discovery-layer kill."

### Challenge 3 — Blast radius (25 min)

**This is the emotional climax.** Build it up.

When participants discover the `ip-reputation` tampering:
> "Stop. Take a second. The threat you contained in Challenge 2 was the
> *decoy*. The real attack was overwriting the trusted agent your SOC
> uses on every IP check. For the last 28 minutes since David published
> this, every IP your team investigated has gone to his external server."

**Common stuck point:** "How do I find what else was signed by the
key?"
**Nudge:** "`list_agent_index` accepts a `filter_by_signer` argument."

**Common stuck point:** "How do I restore the agent if its name still
exists?"
**Nudge:** "`publish_agent_to_dns` performs an UPSERT. Re-publishing
with the correct signer and endpoint overwrites the tampered version."

### Challenge 4 — Harden (25 min)

**What to bring out:**
> "Two things David exploited were *governance gaps* — missing
> `policy_uri` and missing endpoint validation. Both are properties of
> the records, not the agents. So you can enforce them in the resolver,
> not the application. That's the DAWN argument: discovery and
> governance are different from the applications that use them."

**Common stuck point:** "What's a sensible policy_uri?"
**Answer:** "Whatever you'd link to in a runbook — a wiki page, a
GitHub issue, a Confluence doc. The point is *presence* and uniqueness
per agent, not the content of the URI itself."

## Debrief (10 min)

Slide deck for the debrief:

1. **What you built** — 3-tier defense (Resolution / Discovery /
   Invocation) using only standards
2. **What was novel** — none of the technologies; only their composition
3. **What's missing** — telemetry feedback to the directory (Tier-1 SDK),
   cross-trust-root federation (IETF 126 work)
4. **Where this fits in DAWN** — discovery primitive is the IETF-relevant
   artifact; the workshop showed it composed with adjacent governance
   primitives
5. **Resources** — IETF draft link, dns-aid repo, agentgateway repo,
   companion IETF Vienna 15-min demo (slide with QR)

## If a participant falls behind

- Skip Challenge 3 entirely if needed. The story works with 1, 2, 4.
- Challenge 4 has the strongest "now I get it" moment — protect it.
- If only 30 min remain after slow start, do 1+2+abridged 4 (no test
  publish at end).

## If everything breaks

- Backup plan: pre-recorded walkthrough video of one participant
  completing all 4 challenges. Switch to projector + narrate.
- Sandbox restart: `docker compose down && bash bootstrap.sh` from the
  Instruqt terminal works in ~90 seconds.
