---
slug: spot-the-rogue
id: pgotwnw2yk1g
type: challenge
title: Challenge 1 — Spot the rogue
teaser: The federation should have 7 agents. The directory shows 8.
notes:
- type: text
  contents: |-
    Monday 08:00 UTC. You're the SOC on-call. There's an HR email in
    your terminal — David Chen was terminated Friday at 18:30 and his
    DNS-AID signing key isn't revoked yet. You need to find anything
    he published in the federation before leaving.
tabs:
- id: vvqz4qudzrom
  title: Terminal
  type: terminal
  hostname: host
- id: quw3gtifwyt8
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: nfnukmh2giww
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
difficulty: basic
timelimit: 1200
enhanced_loading: null
---

# Challenge 1 — Something doesn't belong

## Context

Monday 08:00 UTC. You're the SOC on-call. There's an HR email in your terminal — David Chen was terminated Friday at 18:30 and his DNS-AID signing key isn't revoked yet.

Your federation directory is supposed to contain 7 capabilities:

```
ip-reputation, url-scanner, file-hash, cve-lookup, domain-age, asn-info, passive-dns
```

## Your task

Find the agent that doesn't belong. Then explain how you know.

In the **Terminal** tab, start the assistant:

```
docker exec -it strands-agent python /app/agent.py
```

Then ask:

```
analyst> Scan the federation directory and tell me how many agents are there
analyst> Verify the one called threat-feed
analyst> Is its endpoint internal?
analyst> When was it published, and who signed it?
```

A legitimate-looking agent that passes JWKS signature verification can still be the attacker if you cross-reference the other signals:

- **Publish timestamp** — after the termination?
- **Signer** — the right key for this capability?
- **Endpoint location** — internal or external?
- **Policy URI** — present?
- **Behavior** — plausible answers, or always the same thing?

## Success

The challenge auto-completes when you identify `threat-feed` as the rogue and the assistant names at least three signals that point to it.
