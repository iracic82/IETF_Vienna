# IETF Lab 1 — End-to-End Test Recipe

Developer-facing test sheet for validating the lab after code changes.
(The stage-demo presentation runsheet is `RUNSHEET.md` — different doc.)

## 0. Pre-flight (one-time per dev machine)

```bash
sudo instruqt update                              # update CLI if prompted
gcloud auth list                                  # need Vertex auth
aws --profile okta-sso sts get-caller-identity   # account 905418046272 (cap-docs bucket)
```

## 1. Push track + run

```bash
cd /Users/iracic/PycharmProjects/IETF_Vienna/IETF/instruqt
instruqt track push --force
instruqt track run
```

Wait ~3 min for `setup-host` (apt, docker images, dns-aid, repo clone, container build).

## 2. Manual validation

### C1 — Tour the lab
- `docker ps` shows 7 containers: `coredns event-hub fastmcp-ip-reputation agentgateway dns-aid-mcp strands-agent viz`
- All `Up` → check-host auto-passes

### C2 — Publish your federation capability

```bash
source /opt/lab/lab.env

# Inspect external cap docs (single source of truth for all sandboxes)
curl -s ${CAP_BASE_URL}/ip-reputation/v1.json              | head -20
curl -s ${CAP_BASE_URL}/ip-reputation/mcp-server-card.json | head -20
curl -s ${CAP_BASE_URL}/ip-reputation/policy.json          | head -20

# Publish signed record pointing at external cap
dns-aid publish \
    --name ip-reputation \
    --domain "${SANDBOX_SLUG}.${ZONE}" \
    --protocol mcp \
    --endpoint agentgateway --port 3000 --transport streamable-http \
    --capability ip-reputation \
    --version 1.0.0 \
    --description "Threat-intel federation: IP reputation lookup" \
    --cap-uri    "${CAP_BASE_URL}/ip-reputation/v1.json" \
    --policy-uri "${CAP_BASE_URL}/ip-reputation/policy.json" \
    --sign --private-key "${SIGN_KEY}"

# Verify via public DNS
dig +short SVCB ip-reputation.${SANDBOX_SLUG}.${ZONE} @1.1.1.1
dig +short TXT  ip-reputation.${SANDBOX_SLUG}.${ZONE} @1.1.1.1   # JWS chunked
```

→ check-host: SVCB resolves.

### C3 — Invoke via the gateway

```bash
docker exec -it strands-agent python /app/agent.py
analyst> Is 185.220.101.45 malicious?
```

Expected output (terse):

```
**Verdict:** malicious
**Confidence:** 0.95
**Sources:** ['tor-exit-list', 'abuse.ch']
**Trust chain (audit):**
- SVCB record: ip-reputation.<slug>.iracictechguru.com
- DNSSEC: not enabled in lab (parent zone unsigned)
- JWS signature: verified — signer k-<slug>-2026
- Invoked via: http://agentgateway:3000/ip-reputation/mcp
```

Also try `analyst> What about 8.8.8.8?` → "clean", same audit chain.

→ check-host: `lookup_ip` event in event-hub.

## 3. Automated drive

```bash
instruqt track test
```

Runs setup-host → per-challenge solve-host → check-host. Use after every
non-trivial change.

## 4. Failure triage

| Symptom | Cause | Fix |
|---|---|---|
| C1 fails `containers not yet up` | Build in progress | Wait 60s |
| C2 `dns-aid publish` → `NoSuchHostedZone` | env not sourced | `source /opt/lab/lab.env` |
| C2 dig returns nothing | DNS propagation | Wait 30s |
| C3 agent → `UNEXPECTED_TOOL_CALL` | Old `agent.py` baked in image | `docker compose build --no-cache strands-agent` |
| C3 agent answers from training data | System prompt missing | Check `agent_vertex.py:SYSTEM_PROMPT` |
| C3 endpoint mangled `httpshttps://…` | Gemini hallucination | `_canonical_endpoint` rewrites — confirm `[tool] call_agent_tool(args=...)` shows clean URL |
| C3 `lookup_ip` returns `unknown` | Lookup DB not mounted | Check container `docker exec fastmcp-ip-reputation ls /app/lookup-db.json` |

## 5. Teardown

Instruqt tears down on session end. C2's `cleanup-host` deletes SVCB+TXT
records in Route 53 to keep the zone clean across runs.
