# SDK Policy Enforcement — Standalone Test

Verifies the [dns-aid SDK](https://github.com/dns-aid/dns-aid-core/tree/main/src/dns_aid/sdk/policy)
caller-side policy guard correctly gates MCP tool invocations based
on a published policy document.

Built before integrating into the IETF lab's C3 challenge — if this
test passes locally, the same enforcement gets wired into the agent
in C3 as a bonus section.

## What it tests

Single policy doc (`policy.json`) with:

- `allowed_methods: ["initialize", "tools/list", "tools/call"]`
- A CEL rule that allows only `tool_name == 'lookup_ip'` (deny all others)
- `rate_limits` (declared, not exercised by these cases)

Three test cases, all evaluated at `PolicyEnforcementLayer.CALLER`:

| # | Context | Expected |
|---|---|---|
| 1 | `method=tools/call`, `tool_name=lookup_ip` | **ALLOWED** |
| 2 | `method=tools/call`, `tool_name=lookup_url` | **DENIED** (CEL: tool-whitelist) |
| 3 | `method=admin/shutdown` | **DENIED** (allowed_methods) |

## Run

```bash
cd tests/sdk-policy-enforcement
./run.sh
```

Expected output:

```
[test] dns-aid version:
   0.21.2

Loaded policy from: …/policy.json
Rules: allowed_methods=['initialize', 'tools/list', 'tools/call'], cel_rules=['tool-whitelist']

policy.cel_backend             backend=rust
[PASS] ✅ tools/call lookup_ip (whitelisted tool)
        → ALLOWED  (no violations)

[PASS] ❌ tools/call lookup_url (not in whitelist)
        → DENIED   cel:tool-whitelist: Only 'lookup_ip' is permitted by this policy

[PASS] ❌ admin/shutdown (not in allowed_methods)
        → DENIED   allowed_methods: …; cel:tool-whitelist: Only 'lookup_ip' is permitted by this policy

OK: all 3 cases behaved as expected
```

## CEL semantics — a gotcha worth knowing

The dns-aid CEL evaluator interprets each expression as an **assertion
that must hold for the request to be allowed**. If the expression
evaluates falsy, the rule's `effect` fires (deny / warn).

So to "deny everything except lookup_ip", the assertion is:

```
request.tool_name == null || request.tool_name == 'lookup_ip'
```

i.e. *"the request is OK iff tool_name is null (e.g. during initialize)
or it's lookup_ip."* This is the opposite of "if expression is true,
deny" — a common first-instinct mistake (which I made first time).

## When this passes

Move to C3 lab integration — wire `evaluator.evaluate(...)` into
`agent_vertex.py` before each `call_agent_tool` invocation and surface
the result in the audit chain ("SDK guard: allowed/denied").
