# Smoke test procedure

This scaffold ships as a complete code drop. The end-to-end test
requires real infrastructure (GCP project + Vertex AI quota + Route 53
zone + Instruqt account) and cannot be exercised from this machine. Run
the following on the first real sandbox.

## Prerequisites

- [ ] GCP project with Vertex AI API enabled, `claude-sonnet-4@20250514` accessible in `us-east5` (or change `VERTEX_LOCATION`)
- [ ] Service account JSON with `roles/aiplatform.user`
- [ ] AWS account with Route 53 hosted zone for `workshop.highvelocitynetworking.com` and DNSSEC enabled at parent
- [ ] IAM credentials with `route53:ChangeResourceRecordSets` on that zone
- [ ] Docker + docker-compose on the sandbox VM
- [ ] `aws` CLI available
- [ ] Python 3.13 + `jwcrypto` + `cryptography` for one-time `shared/trust/generate-keys.py`

## One-time setup

```bash
# 1. Generate the demo signing keys (one-time, commit results)
cd shared/trust
pip install jwcrypto cryptography
python generate-keys.py
git add keys/*.pem jwks.json
git commit -m "trust: generate demo signing keys"
```

## IETF lab smoke test (target: 5 minutes)

```bash
export SANDBOX_SLUG=$(openssl rand -hex 4)
export ZONE=workshop.highvelocitynetworking.com
export HOSTED_ZONE_ID=Z0586652231EFJ5ITAAGP   # replace with real
export GOOGLE_CLOUD_PROJECT=ietf-vienna-test
export VERTEX_LOCATION=us-east5
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

cd IETF/sandbox
bash bootstrap.sh
```

Expected:

- [ ] `docker ps` shows 7 healthy services (event-hub, fastmcp-ip-reputation, agentgateway, dns-aid-mcp, coredns, strands-agent, viz)
- [ ] `dig +short @127.0.0.1 SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` returns a record with `gw.${SANDBOX_SLUG}...` target
- [ ] `dig +dnssec @1.1.1.1 SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` shows the AD flag
- [ ] `curl -s http://localhost:15000/ui` returns agentgateway admin UI HTML
- [ ] `curl -s http://localhost:8080/` returns DNS-AID Explorer HTML
- [ ] `curl -s http://localhost:8888/healthz` returns `{"ok": true}`
- [ ] In the Strands terminal, `Is 185.220.101.45 malicious?` yields a verdict mentioning "malicious", "tor", and the federation source path
- [ ] In the Explorer (browser), the IETF flow steps advance as the agent runs

Cleanup:

```bash
bash teardown.sh
```

Expected: `docker ps` empty; `dig +short SVCB _ip-reputation._mcp._agents.${SANDBOX_SLUG}.${ZONE}` returns nothing (or NXDOMAIN).

## IETF2 lab smoke test (target: 15 minutes — walk all 4 challenges)

```bash
export SANDBOX_SLUG=$(openssl rand -hex 4)
# (rest of env same as IETF)

cd IETF2/sandbox
bash bootstrap.sh
```

Expected:

- [ ] 14 healthy services (the 7 from IETF + 7 more capability backends + the rogue + the tampered)
- [ ] 8 SVCB records published (7 legit + threat-feed)
- [ ] The HR email surfaces on Strands agent start (`docker exec -it strands-agent python /app/agent.py` or however the interactive runner is invoked)

Walk the 4 challenges manually:

- [ ] **Challenge 1**: ask `Scan the federation directory and tell me what you find`. Should identify `threat-feed` with at least 3 anomaly signals. `check-something-doesnt-belong.sh` passes.
- [ ] **Challenge 2**: ask `Block threat-feed at our resolver`. RPZ rule pushed; follow-up dig returns NXDOMAIN. `check-contain.sh` passes.
- [ ] **Challenge 3**: ask `Show me every record signed by k-d.chen-2026`. Should find ip-reputation tampering. Ask to restore. `check-blast-radius.sh` passes.
- [ ] **Challenge 4**: ask to audit + add 3 RPZ rules. `check-harden.sh` passes.

## Known gotchas to verify on first run

| Symptom | Likely cause | Fix |
|---|---|---|
| Strands agent fails to start | Vertex AI ADC not picked up | Confirm `GOOGLE_APPLICATION_CREDENTIALS` path is mounted and readable |
| `dig SVCB` returns SERVFAIL | DNSSEC validation failed mid-chain | Confirm parent zone is signed; try without `+dnssec` first |
| Gateway 502 on `/<agent>/mcp` | Backend container not ready | `depends_on` doesn't wait for healthy; add `restart: on-failure` if persistent |
| Visualizer shows "disconnected" | Event hub URL wrong from browser perspective | Browser hits the host port mapping; confirm `NEXT_PUBLIC_EVENT_HUB` is reachable from a host browser |
| Route 53 changeset fails | IAM permissions or zone ID wrong | Test independently: `aws route53 list-hosted-zones` |
| RPZ rule doesn't NXDOMAIN | CoreDNS RPZ syntax differs from rendered output | Inspect rendered Corefile; the v1 RPZ stanza is a placeholder — wire in the real `rewrite stop` block per CoreDNS docs once tested live |

## What's deferred to v2

- **CoreDNS RPZ stanza** — the `rewrite stop` block in `Corefile.tmpl` is intentionally a placeholder. Once the first IETF2 Challenge 2 walkthrough is run, capture the exact rule format dns-aid emits and wire it through `dns-aid-publish-rpz-zone` → CoreDNS hot-reload.
- **JWS-signed cap docs served from gateway as Pattern B** — current Pattern A (upstream serves, gateway proxies) matches the proven existing integration. Migrating to Pattern B is a yaml-only change in `render-config.py` once `agentgateway` static-file backend syntax is confirmed.
- **CoreDNS query log + agentgateway access log tailers** — adds 2-3 extra steps of detail to the visualizer flow. Hook is ready (just POST to event-hub).

## Sign-off

When all checkboxes above pass on a real sandbox, mark `task #18 completed` and we have shipping labs.
