# Trust — JWKS keys and cap-doc signing

Two demo keys, both RSA-2048, both committed to the repo. These are
**lab keys**, not production secrets.

| Key ID | Role | Used by |
|---|---|---|
| `k-ops-team-2026` | Legitimate org signing key | All seven federation agents |
| `k-d.chen-2026`   | Compromised — terminated employee's key | The rogue agent + tampered `ip-reputation` in IETF2 |

## First-time setup (one-time, per repo clone)

```bash
cd shared/trust
pip install jwcrypto cryptography
python generate-keys.py
```

This writes:
```
shared/trust/keys/k-ops-team-2026.pem
shared/trust/keys/k-d.chen-2026.pem
shared/trust/jwks.json
```

Commit all three.

## Signing a cap doc

```bash
python sign-cap.py --key k-ops-team-2026 --in cap.json --out cap.json.jws
```

For the labs we sign each agent's cap doc at build time and ship the
signed bytes inside the FastMCP container (Pattern A: upstream serves,
gateway proxies). The cap-sha256 referenced from SVCB key65401 is computed
over the signed bytes.

## Verifying

```bash
python verify-cap.py --in cap.json.jws
```

Used in `dns-aid-mcp`'s `verify_agent_dns` tool path — already wired
through the dns-aid library. Verify-cap.py here is a debugging
convenience.

## DNS publication

The JWKS document is served at:
```
https://${SANDBOX_SLUG}.workshop.highvelocitynetworking.com/.well-known/jwks.json
```

For the labs, all sandboxes share one JWKS doc — published from this
repo's `jwks.json` to a static endpoint (S3 + CloudFront, or pinned in
agentgateway as a static-file route). See `IETF/sandbox/` and
`IETF2/sandbox/` for the per-lab wiring.
