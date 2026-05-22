---
slug: harden
id: wpqaiqnuzhnc
type: challenge
title: Challenge 4 — Harden
teaser: Two threats contained. Make sure this class of attack can't happen again.
notes:
- type: text
  contents: |-
    Add three RPZ-enforced governance rules so future ungoverned or
    external agents can't be discovered, regardless of who signed them.
tabs:
- id: i9pl3culbz5c
  title: Terminal
  type: terminal
  hostname: host
- id: 3snyfuphhsho
  title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- id: 8fzbukauyded
  title: agentgateway UI
  type: service
  hostname: host
  port: 15000
difficulty: intermediate
timelimit: 1500
enhanced_loading: null
---

# Challenge 4 — Harden

## Context

You contained `threat-feed`. You restored `ip-reputation`. You revoked David's key. The acute incident is over.

But the root cause is still open: some federation agents have no `policy_uri`, and nothing checked endpoint locations. David exploited both gaps.

## Your task

Add three RPZ-enforced governance rules to your federation zone:

```
Rule 1 — No policy_uri      → NXDOMAIN
Rule 2 — External endpoint  → NXDOMAIN
Rule 3 — Signed by k-d.chen-2026 → NXDOMAIN  (already added in Challenge 3)
```

Ask the assistant:

```
analyst> Audit every agent — which ones are missing a policy_uri?
analyst> Add policy URIs to any that are missing one
analyst> Now create governance RPZ rules: no policy → block, external endpoint → block
```

## Success

Auto-completes when at least 3 RPZ rules are active (no-policy, external-endpoint, banned-signer).
