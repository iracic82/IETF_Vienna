---
slug: blast-radius
id: h7za2bqwcy9m
type: challenge
title: Challenge 3 — Blast radius
teaser: David had 28 minutes after publishing the rogue. What else did he touch?
notes:
- type: text
  contents: |-
    The decoy is contained. But the real attack is what David did with
    his key in the 28 minutes between publishing the rogue and leaving
    the building.
tabs:
- id: avniebdfla9s
  title: Terminal
  type: terminal
  hostname: host
- id: rltqxnodfwof
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: ydld0ixdizya
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
difficulty: intermediate
timelimit: 1500
enhanced_loading: null
---

# Challenge 3 — Blast radius

## Context

`threat-feed` is contained. But David Chen had **28 minutes** between publishing the rogue at 22:47 and leaving the building. His signing key worked the whole time.

What else did he sign?

## Your task

```
analyst> Show me every record signed by k-d.chen-2026
```

You'll find two:

1. `threat-feed` — already contained.
2. `ip-reputation` — re-signed by David at 22:51, originally signed by `k-ops-team-2026`.

The second is the **real** attack. `ip-reputation` is a trusted federation capability the SOC has used since March. David didn't add a new agent — he tampered with an existing one. The endpoint was swapped to an external server he controls. Every IP your SOC checks goes to him.

## Restore

```
analyst> Restore ip-reputation with the ops team key and the internal endpoint
analyst> Now block David's key everywhere — any record signed by k-d.chen-2026 → NXDOMAIN
```

## Success

Auto-completes when `verify_agent_dns` on `ip-reputation` shows signer = `k-ops-team-2026` AND an RPZ rule blocks the `k-d.chen-2026` key id.
