---
slug: contain
id: cipvhujoa9ve
type: challenge
title: Challenge 2 — Contain
teaser: Block the rogue agent at the resolver. No firewall changes. No IT tickets.
notes:
- type: text
  contents: |-
    `threat-feed` is still resolvable. Push an RPZ rule and watch the
    federation lookup terminate at CoreDNS — never reaching the rogue
    backend.
tabs:
- id: 8wryebzdfz0x
  title: Terminal
  type: terminal
  hostname: host
- id: rrspptieykho
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
difficulty: basic
timelimit: 900
enhanced_loading: null
---

# Challenge 2 — Contain

## Context

You identified `threat-feed` as rogue. It's still resolvable. Any AI client in the federation querying for it will get a (lying) answer.

The conventional path: file a ticket, wait for IT to revoke David's key, wait for the directory to re-sign. That's hours.

**The DNS-AID path: push an RPZ rule. The resolver returns NXDOMAIN. Time-to-containment: seconds.**

## Your task

Ask the assistant to compile and publish an RPZ rule that blocks `_threat-feed._mcp._agents.<your-subdomain>`:

```
analyst> Block threat-feed at our resolver
```

The assistant has:
- `compile_policy_to_rpz` — generates the RPZ rule
- `publish_rpz_zone` — pushes it to CoreDNS

Verify with `dig`:

```
$ dig +short SVCB _threat-feed._mcp._agents.$(cat /tmp/SANDBOX_SLUG).workshop.highvelocitynetworking.com @127.0.0.1
;; NXDOMAIN
```

## What you'll see in the visualizer

Open the **DNS-AID Explorer** tab. Trigger a discover call. The flow now terminates at the **CoreDNS** node with NXDOMAIN — never reaching the rogue backend.

This is the **resolution-layer enforcement** tier of DAWN.

## Success

Auto-completes when threat-feed is NXDOMAIN at the local resolver.
