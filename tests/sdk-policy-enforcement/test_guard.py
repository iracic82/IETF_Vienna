"""Standalone test of the dns-aid SDK caller-side policy guard.

Goal: prove the SDK's policy evaluator correctly gates an MCP tool
invocation based on the target's published policy document.

We exercise THREE scenarios against the same policy.json:

  1. tools/call with tool_name='lookup_ip' — should be ALLOWED
     (whitelisted via the CEL rule's negation)
  2. tools/call with tool_name='lookup_url' — should be DENIED
     (the CEL rule fires: not 'lookup_ip' → deny)
  3. method='admin/shutdown' — should be DENIED
     (not in allowed_methods)

We bypass the convenience wrapper `check_target_policy(...)` (which
doesn't expose tool_name) and use PolicyEvaluator + PolicyContext
directly so we can drive the tool-level CEL rule.

Run via run.sh — pip install + python.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

from dns_aid.sdk.policy.evaluator import PolicyEvaluator
from dns_aid.sdk.policy.models import PolicyContext
from dns_aid.sdk.policy.schema import PolicyDocument, PolicyEnforcementLayer


# evaluator.fetch() only accepts HTTPS URLs (URL-safety guard). For the
# local standalone test we load the policy.json directly and parse it
# into a PolicyDocument; the evaluator's evaluate() takes the model.
# In the lab integration the agent will use evaluator.fetch() against
# the real S3 HTTPS URL.
POLICY_PATH = pathlib.Path(__file__).parent / "policy.json"


def _fmt(result) -> str:
    """Compact pretty-print of a PolicyResult."""
    flag = "ALLOWED" if result.allowed else "DENIED "
    if result.violations:
        return f"{flag}  {result.reason}"
    return f"{flag}  (no violations)"


async def main() -> int:
    evaluator = PolicyEvaluator()
    policy_doc = PolicyDocument.model_validate_json(POLICY_PATH.read_text())
    print(f"Loaded policy from: {POLICY_PATH}")
    print(f"Rules: allowed_methods={policy_doc.rules.allowed_methods}, "
          f"cel_rules={[r.id for r in (policy_doc.rules.cel_rules or [])]}")
    print()

    cases = [
        (
            "✅ tools/call lookup_ip (whitelisted tool)",
            PolicyContext(
                caller_id="test-caller",
                protocol="mcp",
                method="tools/call",
                tool_name="lookup_ip",
            ),
            True,
        ),
        (
            "❌ tools/call lookup_url (not in whitelist)",
            PolicyContext(
                caller_id="test-caller",
                protocol="mcp",
                method="tools/call",
                tool_name="lookup_url",
            ),
            False,
        ),
        (
            "❌ admin/shutdown (not in allowed_methods)",
            PolicyContext(
                caller_id="test-caller",
                protocol="mcp",
                method="admin/shutdown",
            ),
            False,
        ),
    ]

    failures = 0
    for label, ctx, expected_allowed in cases:
        result = evaluator.evaluate(
            policy_doc, ctx, layer=PolicyEnforcementLayer.CALLER,
        )
        ok = result.allowed == expected_allowed
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {label}")
        print(f"        → {_fmt(result)}")
        if not ok:
            failures += 1
            print(f"        ↳ expected allowed={expected_allowed}, got {result.allowed}")
        print()

    if failures:
        print(f"FAILED: {failures}/{len(cases)} cases did not match expectation")
        return 1
    print(f"OK: all {len(cases)} cases behaved as expected")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
