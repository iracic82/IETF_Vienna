"""DNS-AID SDK caller-side policy guard — reusable wrapper for an AI agent.

How to use this in your own agent:

1. Install dns-aid with the [cel] extra so CEL rules can be evaluated::

       pip install 'dns-aid[mcp,cel]>=0.21.0'

2. Whenever your agent is about to invoke a discovered MCP capability,
   call :func:`evaluate_call` with the target's published policy URL
   (the ``policy_uri`` SVCB SvcParam or ``policy_uri`` field on the
   cap document) and the request context (method, tool name, etc.).

3. If :attr:`PolicyDecision.allowed` is ``False`` your agent MUST NOT
   make the invocation. Surface :attr:`PolicyDecision.reason` to the
   user / audit log so the denial is observable.

Architecture context — DNS-AID defines three independent enforcement
points, all reading the SAME policy document:

  * Layer 0 — DNS resolver (bind-aid RPZ compiled from the same policy)
  * Layer 1 — caller-side SDK (THIS module)
  * Layer 2 — target-side ASGI middleware on the agent server

This module wraps Layer 1. The same ``PolicyEvaluator`` runs in all
three layers, so a deny decision here means the call would also be
denied by Layer 2 — but Layer 1 saves the network round-trip.

Reference implementation: https://github.com/infobloxopen/dns-aid-core
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass


__all__ = ["PolicyDecision", "evaluate_call", "SDKUnavailable"]


@dataclass(frozen=True)
class PolicyDecision:
    """The outcome of a Layer 1 policy evaluation.

    Always safe to consume regardless of whether the SDK was actually
    invoked — see :func:`evaluate_call` for fail-open semantics.
    """

    allowed: bool
    reason: str           # Human-readable explanation
    policy_uri: str | None  # Where the policy came from (for audit)
    layer: str = "layer1-caller-sdk"


class SDKUnavailable(RuntimeError):
    """Raised when the caller has explicitly requested strict-mode
    enforcement but the dns-aid SDK isn't installed. Default behaviour
    is fail-open."""


def evaluate_call(
    policy_uri: str | None,
    *,
    tool_name: str | None,
    method: str = "tools/call",
    protocol: str = "mcp",
    caller_id: str = "dns-aid-agent",
    strict: bool = False,
) -> PolicyDecision:
    """Evaluate a target's published policy against an outgoing call.

    Args:
        policy_uri: The HTTPS URL of the target's policy document
            (from SVCB ``policy_uri`` SvcParam / cap doc). If ``None``,
            returns ``allowed=True`` with a "no policy advertised" reason.
        tool_name: The MCP tool the agent intends to call (e.g.
            ``lookup_ip``). Becomes ``request.tool_name`` in CEL rules.
        method: The MCP JSON-RPC method, typically ``tools/call``.
        protocol: The wire protocol — ``mcp`` or ``a2a``.
        caller_id: An opaque identifier for the caller (logged into
            policy telemetry; not used for authorization).
        strict: If ``True``, raise :class:`SDKUnavailable` when the
            dns-aid SDK is not installed. Defaults to ``False``
            (fail-open with a clear reason).

    Returns:
        :class:`PolicyDecision` — inspect ``.allowed`` and act.
        Never silently denies: the caller always gets a textual reason.
    """
    if not policy_uri:
        return PolicyDecision(
            allowed=True,
            reason="no policy_uri advertised by target — fail-open",
            policy_uri=None,
        )

    # Late import so this module is importable without the SDK present
    # (and so that a missing SDK results in a clear PolicyDecision
    # rather than an ImportError at module-load time).
    try:
        from dns_aid.sdk.policy.evaluator import PolicyEvaluator
        from dns_aid.sdk.policy.models import PolicyContext
        from dns_aid.sdk.policy.schema import PolicyDocument, PolicyEnforcementLayer
    except ImportError as exc:
        if strict:
            raise SDKUnavailable(
                "dns-aid SDK not installed; install with: pip install 'dns-aid[mcp,cel]>=0.21.0'"
            ) from exc
        return PolicyDecision(
            allowed=True,
            reason=f"dns-aid SDK not installed ({exc}) — fail-open",
            policy_uri=policy_uri,
        )

    # Fetch the policy document. PolicyEvaluator has a built-in HTTPS-only
    # fetcher with URL-safety checks; we use our own urllib for two reasons:
    #   (a) we want explicit control over the timeout
    #   (b) the SDK's evaluator.fetch() is async and we want a sync API
    # The resulting bytes get parsed by PolicyDocument.model_validate_json,
    # which is the same validator the SDK uses internally.
    try:
        with urllib.request.urlopen(policy_uri, timeout=5) as resp:
            doc = PolicyDocument.model_validate_json(resp.read())
    except Exception as exc:  # noqa: BLE001 — network/parse error reported as fail-open
        return PolicyDecision(
            allowed=True,
            reason=f"policy fetch failed ({type(exc).__name__}: {exc}) — fail-open",
            policy_uri=policy_uri,
        )

    # Build the request context. PolicyContext has many optional fields
    # (geo_country, tls_version, dnssec_validated, etc.) for richer
    # decisions — populate what your agent actually knows.
    ctx = PolicyContext(
        caller_id=caller_id,
        caller_domain=os.environ.get("DNS_AID_CALLER_DOMAIN"),
        protocol=protocol,
        method=method,
        tool_name=tool_name,
    )

    result = PolicyEvaluator().evaluate(
        doc, ctx, layer=PolicyEnforcementLayer.CALLER,
    )

    if result.allowed:
        return PolicyDecision(
            allowed=True,
            reason="ALLOWED by SDK caller guard",
            policy_uri=policy_uri,
        )
    return PolicyDecision(
        allowed=False,
        reason=f"DENIED: {result.reason}",
        policy_uri=policy_uri,
    )
