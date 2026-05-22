---
slug: publish-your-agent
type: challenge
title: 2. Publish your federation capability
teaser: Use the dns-aid CLI to publish your ip-reputation capability into Route 53.
notes:
- type: text
  contents: |-
    Now you publish — by hand — the DNS-AID record that lets other
    federation members discover your capability. The `dns-aid` CLI talks
    to Route 53 directly using the credentials Instruqt already injected.
tabs:
- title: Terminal
  type: terminal
  hostname: host
- title: DNS-AID Explorer
  type: service
  hostname: host
  port: 8080
- title: Editor
  type: code
  hostname: host
  path: /root
difficulty: basic
timelimit: 600
enhanced_loading: null
---

# 2. Publish your federation capability

## Load the env

```bash
source /tmp/sandbox.env
echo "subdomain  = ${SANDBOX_SLUG}.${ZONE}"
echo "gw host    = gw.${SANDBOX_SLUG}.${ZONE}"
echo "backend    = ${DNS_AID_BACKEND}"
echo "zone id    = ${HOSTED_ZONE_ID}"
```

## See what dns-aid can do

```bash
dns-aid --help
dns-aid publish --help
```

## Publish

```bash
dns-aid publish \
    --name ip-reputation \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint "gw.${SANDBOX_SLUG}.${ZONE}" \
    --port 3000 \
    --capability ip-reputation \
    --version 1.0.0 \
    --description "Threat-intel federation: IP reputation lookup"
```

`dns-aid` will create the SVCB + TXT records under your subdomain in Route 53.

## Verify

```bash
# Direct query against a public resolver
dig +short SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE} @1.1.1.1

# Discovery via dns-aid (parses the SVCB + cap doc)
dns-aid discover "${SANDBOX_SLUG}.${ZONE}"
```

You should see the SVCB record pointing at `gw.${SANDBOX_SLUG}.${ZONE}` on port 3000.

## Try it — also publish a second agent

The federation supports more capabilities than just IP reputation. Try publishing one more (the backend container `fastmcp-url-scanner` doesn't exist yet — but the record is what matters here):

```bash
dns-aid publish \
    --name url-scanner \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint "gw.${SANDBOX_SLUG}.${ZONE}" \
    --port 3000 \
    --capability url-scanner \
    --description "Phishing / malware URL verdicts"
```

Then `dns-aid discover` again — see two agents now.

## Success

Auto-completes when at least one `_ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` SVCB record resolves.
