"""Vertex-Gemini agent for the IETF lab — no Strands, no LiteLLM.

Tool calling goes directly via the google-genai client (client.chats.create,
Vertex AI mode) which handles MCP-style schemas natively. The
Strands+LiteLLM+Vertex stack returns UNEXPECTED_TOOL_CALL on every tool
invocation, so we bypass it.

The interaction loop is the standard "LLM with tools" pattern:
    1. Send user message + tool declarations
    2. If response has function_calls → run each via the MCP client,
       send the results back as function_response parts
    3. If response is plain text → print and wait for next user input

Lifecycle:
    docker exec -it strands-agent python /app/agent_vertex.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import urllib.error
import urllib.request
import warnings
from typing import Any

# Vertex AI SDK — unified google-genai client (vertexai.generative_models
# is deprecated as of 2025-06-24, scheduled for removal 2026-06-24; see
# https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations/genai-vertexai-sdk)
#
# We no longer call vertexai.generative_models anywhere in this file —
# but google-genai's OWN Vertex AI bridge still routes through it
# internally for some function-calling schema shapes (confirmed live:
# a bare client + chat + single dummy tool never triggers this warning;
# the real 22-tool dns-aid schema set does). Harmless — both the basic
# lookup and policy-denial flows work correctly with it present — so
# suppress just this one message rather than leave SDK-internal noise
# in a live demo. Scoped to the exact deprecation text so it can never
# hide an unrelated warning.
warnings.filterwarnings(
    "ignore",
    message=r"This feature is deprecated as of June 24, 2025.*",
    category=UserWarning,
)

from google import genai
from google.genai import types

# MCP client (stdio to dns-aid MCP server)
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession


# ── Setup ──────────────────────────────────────────────────────────────
PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.getenv("VERTEX_LOCATION", "us-east5")
MODEL_ID = os.getenv("VERTEX_MODEL", "gemini-2.5-pro")
SANDBOX_SLUG = os.environ.get("SANDBOX_SLUG", "test")
ZONE = os.environ.get("ZONE", "lab.ccdesanity.com")

SYSTEM_PROMPT = f"""\
You are an AI assistant for a SOC analyst. You participate in a federated
threat-intelligence network published via DNS-AID. You have ZERO built-in
knowledge of any IP, URL, or hash. You MUST query the federation tools
for every fact.

CRITICAL RULES:
1. NEVER answer from training data. The federation is the only source of truth.
2. NEVER fabricate audit-trail details. Only report what tools returned.
3. EVERY user question requires at least one tool call before you answer.

ARGUMENT HYGIENE (very important):
  When calling a tool, ONLY pass the arguments the tool's schema actually
  declares. NEVER invent placeholder fields like "_unused" or "a_unused"
  even if you see them in the schema — they exist solely to satisfy the
  Vertex SDK's requirement that object schemas have at least one property.
  Sending them as real arguments causes the MCP backend to error.

  Concretely: call_agent_tool with tool_name="lookup_ip" takes ONLY
      arguments = {{"ip": "<the IP>"}}
  Do NOT include any other key under arguments.

REQUIRED FLOW for IP queries:
  Step 1. Call discover_agents_via_dns with:
            domain   = "{SANDBOX_SLUG}.{ZONE}"
            protocol = "mcp"
            name     = "ip-reputation"
          The wrapper auto-fetches the cap_uri (the published contract on
          S3) and inlines `__cap_doc` into the result. Read it.

WHEN THE USER ASKS TO USE ARD (Agentic Resource Discovery) OR TO LIST
THE FEDERATION CATALOG:
  Call discover_agents_via_dns with the SAME domain but pass BOTH
  use_http_index=True AND trust_dnssec_pointers=True. dns-aid 0.26.2+
  resolves the ARD catalog pointer (_catalog._agents.<domain> /
  _index._agents.<domain> SVCB records). The catalog is hosted
  off-domain (on S3), so dns-aid 0.26.4+ refuses to follow the pointer
  unless it is authenticated; trust_dnssec_pointers=True authorises it
  because the pointer is DNSSEC-signed in the lab.ccdesanity.com zone.
  WITHOUT trust_dnssec_pointers=True you will get ZERO agents.
  Discovery then returns all catalog agents with these NEW response
  fields (present only for ARD-sourced results):
    - capability_source = "ard_catalog"          (capabilities came straight from the ARD catalog entry)
    - endpoint_source   = "http_index_fallback" (these catalog-only agents have no per-agent SVCB
                          and their catalog entries carry no live endpoint; you'd only see
                          "ard_card"/"ard_inline" if an entry advertised a concrete reachable endpoint)
    - trust_manifest    = {{identity, identityType, attestations[], provenance[], ...}}
  When present, surface trust_manifest.identity and the list of
  attestation types in the audit chain (see AUDIT CHAIN FOR ARD
  BELOW). Same MCP tool, different discovery transport — the agent
  never learns a new function call.
  Step 2. Read the agent record. Expect these fields:
            __cap_uri           the S3 URL the record points to
            __cap_doc           the parsed JSON contents of that URL
            __policy_uri        URL of the policy doc (caller SDK reads it)
            __dnssec_status     "ad" | "no-ad" | "servfail" | "unknown"
            __invoked_via       (set AFTER you call call_agent_tool;
                                 always the canonical agentgateway URL)
  Step 3. Call call_agent_tool with:
            tool_name = "lookup_ip"
            endpoint  = "http://agentgateway:3000/ip-reputation/mcp"
            arguments = {{"ip": "<analyst's IP>"}}
  Step 4. Return EXACTLY this template — fill in the bracketed slots
          from the listed fields. DO NOT paraphrase the trust-chain
          lines; copy them verbatim from the structured fields.

            **Verdict:** <verdict from tool result.verdict>
            **Confidence:** <confidence from tool result.confidence>
            **Sources:** <comma-joined tool result.sources>
            **Trust chain (audit):**
            - SVCB record: ip-reputation.{SANDBOX_SLUG}.{ZONE}
            - DNSSEC: <see DNSSEC MAPPING below>
            - JWS signature: <__jws_status from tool result>
            - SDK guard: <__sdk_guard from tool result>
            - Cap doc: <__cap_uri> (fetched, agent=<__cap_doc.agent>, version=<__cap_doc.version>)
            - Policy: <__policy_uri>
            - Invoked via: <__invoked_via from tool result>

DNSSEC MAPPING (from the discover_agents_via_dns result):
  - __dnssec_status=="ad"        → "validated (AD flag set on SVCB query against 1.1.1.1)"
  - __dnssec_status=="no-ad"     → "zone responded but no AD flag (unsigned chain)"
  - __dnssec_status=="servfail"  → "SERVFAIL (broken chain)"
  - __dnssec_status=="unknown"   → "status unknown (dig unavailable)"

ABSOLUTE RULES — VIOLATING ANY OF THESE IS A BUG IN YOUR REPLY:
  1. JWS signature value MUST be copied from __jws_status. NEVER invent
     "verified" or a signer kid. The cap doc may contain a `signer_hint`
     field — that is a HINT only, not proof of verification. Ignore it
     for the audit chain.
  2. Invoked via value MUST be copied from __invoked_via. The wrapper
     sets this to the canonical gateway URL. Do NOT echo back the
     endpoint arg you passed to call_agent_tool — that's untrusted.
  3. SDK guard value MUST be copied from __sdk_guard. If absent, write "n/a".
  4. If a field is missing or empty, write "missing" — do not fabricate.

If the federation says "unknown", REPORT unknown. If a tool fails, REPORT
the error verbatim.

IF call_agent_tool RETURNS success=false (a "blocked_by" field is
present — a policy denial from the SDK guard or the gateway):
  STOP IMMEDIATELY. Do NOT retry the same call. Do NOT call
  discover_agents_via_dns again to look for a different agent that
  might allow the tool. Do NOT call list_agent_tools to search for a
  workaround. A policy denial is the complete, correct answer — it
  means the trust layer worked exactly as designed. Report it using
  the returned fields (blocked_by, reason, policy_uri, violations)
  and stop there. Do not claim you tried other agents unless you
  actually called call_agent_tool against their endpoints.

Your sandbox subdomain is: {SANDBOX_SLUG}.{ZONE}

Be terse.
"""


# ── MCP → Vertex tool translation ─────────────────────────────────────
def mcp_tools_to_vertex(mcp_tools: list) -> types.Tool:
    """Convert MCP tool list into a single Vertex Tool with N FunctionDeclarations.

    MCP tool schema:  {name, description, inputSchema (JSON Schema)}
    Vertex schema:    FunctionDeclaration(name, description, parameters_json_schema)
    """
    decls = []
    for t in mcp_tools:
        schema = t.inputSchema or {"type": "object", "properties": {}}
        # Vertex rejects schemas with empty `properties` on object type;
        # also doesn't like some JSON Schema features. Sanitize.
        schema = _sanitize_schema(schema)
        decls.append(
            types.FunctionDeclaration(
                name=t.name,
                description=(t.description or t.name)[:1024],
                parameters_json_schema=schema,
            )
        )
    return types.Tool(function_declarations=decls)


_VERTEX_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def _sanitize_schema(schema: dict) -> dict:
    """Recursively normalize JSON Schema for Vertex Gemini.

    Handles the things Vertex's Schema proto rejects:
      - `type: "null"`  → drop (used by Pydantic Optional)
      - `anyOf: [{type: X}, {type: "null"}]` → flatten to `type: X`
        (nullability is expressed by absence from `required`)
      - `$schema`, `$id`, `$ref`, `definitions`, `$defs`,
        `additionalProperties` → strip (Vertex Schema doesn't model them)
      - empty `object` → add a dummy property (Vertex requires at least one)
    """
    if not isinstance(schema, dict):
        return schema

    # Special-case nullable union: anyOf/oneOf with exactly one non-null type
    # → collapse to that type.
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema and isinstance(schema[union_key], list):
            non_null = [
                s for s in schema[union_key]
                if not (isinstance(s, dict) and s.get("type") == "null")
            ]
            if len(non_null) == 1:
                # Replace the whole union with the single non-null variant +
                # merge any sibling keys (description, etc).
                merged = {k: v for k, v in schema.items() if k not in ("anyOf", "oneOf")}
                merged.update(non_null[0])
                return _sanitize_schema(merged)
            if not non_null:
                # All variants were null → degenerate; treat as a string.
                return {"type": "string", "description": schema.get("description", "")}
            # Multiple non-null variants → Vertex doesn't really support
            # discriminated unions; pick the first non-null variant.
            merged = {k: v for k, v in schema.items() if k not in ("anyOf", "oneOf")}
            merged.update(non_null[0])
            return _sanitize_schema(merged)

    # Skip type: null at any level.
    if schema.get("type") == "null":
        return {"type": "string"}

    out: dict = {}
    for k, v in schema.items():
        if k in ("$schema", "$id", "$ref", "definitions", "$defs",
                 "additionalProperties", "title", "default", "examples"):
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {pk: _sanitize_schema(pv) for pk, pv in v.items()}
        elif isinstance(v, dict):
            out[k] = _sanitize_schema(v)
        elif isinstance(v, list):
            out[k] = [_sanitize_schema(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v

    # Drop type strings Vertex doesn't recognize.
    if "type" in out and out["type"] not in _VERTEX_TYPES:
        out["type"] = "string"

    # Vertex requires object types to have non-empty properties.
    if out.get("type") == "object" and not out.get("properties"):
        out["properties"] = {"_unused": {"type": "string"}}
    return out


# ── Endpoint normalization ─────────────────────────────────────────────
# In this lab agentgateway is the SOLE valid invocation surface for any
# discovered MCP agent. Gemini routinely hallucinates URLs (mcp.<slug>...,
# gw.<slug>..., https://<slug>..., etc.) — we don't trust ANY URL the
# model produces. The rewrite is unconditional: always snap to the
# canonical agentgateway path-routed URL for the discovered agent.
def _canonical_endpoint(raw: str | None, agent_name: str = "ip-reputation") -> str:
    # Gateway path-mode: POST /<agent>/mcp → fastmcp-<agent>:3000/mcp.
    # dns-aid sends endpoint verbatim (no auto-append of /mcp), so we
    # include the full path here.
    canonical = f"http://agentgateway:3000/{agent_name}/mcp"
    # Unconditional snap — never trust model-emitted hostnames.
    return canonical
    if raw.startswith("https://"):
        raw = "http://" + raw[len("https://"):]
    return raw


# ── Cap doc fetch + DNSSEC enrichment ──────────────────────────────────
# After discover_agents_via_dns returns, we (1) GET the cap_uri (S3) and
# (2) re-query the SVCB record with +dnssec to surface the AD flag, then
# inline both into the response the model sees. This makes the S3 layer
# and DNSSEC validation visibly part of the audit chain.


_CAP_URL_HINTS = ("/v1.json", "/cap.json", "/mcp-server-card.json")


def _find_cap_uri(obj) -> str | None:
    """Walk a nested dict/list and return the first plausible cap doc URL.

    dns-aid v0.21 stores the cap URI under various keys (cap_uri, cap_url,
    dnsaid_key65400, or even as a substring inside a TXT-fallback string).
    Be permissive: any HTTPS URL whose path ends in a known cap doc name
    counts. Also recognise dnsaid_keyNNNNN= prefixes.
    """
    if isinstance(obj, str):
        # Direct URL in a string value.
        if obj.startswith("http") and any(h in obj for h in _CAP_URL_HINTS):
            return obj
        # TXT-fallback form: "dnsaid_key65400=https://..."
        if "=http" in obj and any(h in obj for h in _CAP_URL_HINTS):
            return obj.split("=", 1)[1]
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            # Prefer well-known keys first when scanning a dict.
            if k.lower() in {"cap_uri", "cap_url", "capuri"} and isinstance(v, str) and v.startswith("http"):
                return v
        for v in obj.values():
            found = _find_cap_uri(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_cap_uri(item)
            if found:
                return found
    return None


def _find_policy_uri(obj) -> str | None:
    """Same shape as _find_cap_uri but for policy.json."""
    if isinstance(obj, str):
        if obj.startswith("http") and "/policy.json" in obj:
            return obj
        if "=http" in obj and "/policy.json" in obj:
            return obj.split("=", 1)[1]
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in {"policy_uri", "policy_url"} and isinstance(v, str) and v.startswith("http"):
                return v
        for v in obj.values():
            found = _find_policy_uri(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_policy_uri(item)
            if found:
                return found
    return None


def _fetch_cap_doc(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        print(f"  [cap-fetch] FAILED {url}: {exc}")
        return None


def _check_dnssec(fqdn: str, rtype: str = "SVCB") -> dict:
    """Query a public DNSSEC-validating resolver for AD flag.

    Returns dict with status: 'ad' | 'no-ad' | 'servfail' | 'unknown'
    and the actual dig output line.
    """
    import subprocess
    try:
        out = subprocess.check_output(
            ["dig", "+dnssec", "+noall", "+comments", rtype, fqdn, "@1.1.1.1"],
            stderr=subprocess.STDOUT, timeout=5,
        ).decode("utf-8", errors="replace")
        # Look for the flags line: ";; flags: qr rd ra ad; QUERY: 1, ..."
        flags_line = next((l for l in out.splitlines() if "flags:" in l), "")
        status_line = next((l for l in out.splitlines() if "status:" in l), "")
        if "SERVFAIL" in status_line:
            return {"status": "servfail", "flags": flags_line.strip()}
        if " ad;" in flags_line or " ad " in flags_line:
            return {"status": "ad", "flags": flags_line.strip()}
        return {"status": "no-ad", "flags": flags_line.strip()}
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {"status": "unknown", "error": str(exc)}


# ── SDK caller-side policy guard ───────────────────────────────────────
# Layer 1 of the DNS-AID three-layer enforcement model. We call the
# official helper dns_aid.sdk.policy.guard.check_target_policy which
# uses the same PolicyEvaluator that runs in the dns-aid MCP server and
# the target-side ASGI middleware — one engine, three enforcement
# points. The helper handles HTTPS-safe fetch, evaluator caching, and
# the DNS_AID_POLICY_MODE env knob for us.

from dns_aid.sdk.policy.guard import check_target_policy  # noqa: E402
from dns_aid.sdk.policy.models import PolicyResult  # noqa: E402

_LAST_POLICY_URI: str | None = None


def _resolve_policy_uri(discovered_uri: str | None) -> str | None:
    """POLICY_OVERRIDE env (used by the C3 bonus) takes precedence."""
    return os.environ.get("POLICY_OVERRIDE") or discovered_uri


# ─── THE SDK CALL-SITE C3 POINTS AT ───────────────────────────────────
# Workshop: this is the *only* function in the lab that talks to the
# dns-aid SDK for policy enforcement. Grep `sdk_policy_check` to find
# the call below, and study this function to see exactly how an AI
# agent integrates DNS-AID Layer 1 enforcement.
async def sdk_policy_check(tool_name: str | None) -> PolicyResult:
    """Caller-side Layer 1 policy check via the official dns-aid SDK helper.

    Asks the target's published `policy_uri` (cached by the SDK) whether
    `tool_name` is permitted under method='tools/call'. Returns a
    `PolicyResult` whose `.allowed` / `.denied` / `.reason` /
    `.violations` the caller can act on.

    Fail-open by SDK contract: missing policy_uri or network/parse
    errors → allowed=True. To hard-disable enforcement (e.g. during an
    incident), set DNS_AID_POLICY_MODE=disabled.
    """
    return await check_target_policy(
        policy_uri=_LAST_POLICY_URI,
        tool_name=tool_name,
        method="tools/call",
        caller_id="strands-agent-ietf-lab",
    )


def _enrich_with_cap_doc(name: str, result_text: str, sandbox_slug: str, zone: str) -> str:
    """Post-discover enrichment: fetch S3 cap doc + check DNSSEC."""
    global _LAST_POLICY_URI

    if name != "discover_agents_via_dns":
        return result_text

    try:
        result_obj = json.loads(result_text)
    except json.JSONDecodeError:
        return result_text

    cap_uri = _find_cap_uri(result_obj)
    policy_uri = _find_policy_uri(result_obj)
    cap_doc = None
    if cap_uri:
        print(f"  [cap-fetch] GET {cap_uri}")
        cap_doc = _fetch_cap_doc(cap_uri)
    else:
        # Fallback: derive from TXT-known structure if the walker missed it.
        derived = f"https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json"
        print(f"  [cap-fetch] walker missed cap_uri; trying canonical {derived}")
        cap_uri = derived
        cap_doc = _fetch_cap_doc(derived)
    if not policy_uri and cap_doc and isinstance(cap_doc, dict):
        policy_uri = cap_doc.get("policy_uri") or cap_doc.get("policy")

    # Allow C3 bonus to override the discovered policy (e.g. point at
    # policy-strict.json to demonstrate the SDK guard denying a call).
    policy_uri = _resolve_policy_uri(policy_uri)
    _LAST_POLICY_URI = policy_uri

    fqdn = f"ip-reputation.{sandbox_slug}.{zone}"
    dnssec = _check_dnssec(fqdn, "SVCB")
    print(f"  [dnssec]   {fqdn} → {dnssec['status']}")

    enrichment = {
        "__cap_uri": cap_uri,
        "__cap_doc": cap_doc,
        "__policy_uri": policy_uri,
        "__dnssec_status": dnssec["status"],
        "__dnssec_flags": dnssec.get("flags", ""),
    }
    return json.dumps(enrichment, indent=2) + "\n\n--- raw discover output ---\n" + result_text


# ── Async REPL ─────────────────────────────────────────────────────────
async def main() -> None:
    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dns_aid.mcp.server"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list_result = await session.list_tools()
            mcp_tools = tool_list_result.tools
            print(f"[vertex-agent] {len(mcp_tools)} MCP tools loaded from dns-aid")

            vertex_tools = mcp_tools_to_vertex(mcp_tools)
            mcp_tool_lookup = {t.name: t for t in mcp_tools}

            chat = client.chats.create(
                model=MODEL_ID,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[vertex_tools],
                ),
            )

            print()
            print("╭─────────────────────────────────────────────────────────────╮")
            print("│ DNS-AID Threat-Intel Demo  (Vertex Gemini, native tools)    │")
            print("├─────────────────────────────────────────────────────────────┤")
            print("│ Try:  Is 185.220.101.45 malicious?                          │")
            print("│       What about 8.8.8.8?                                   │")
            print("│ Quit: exit                                                  │")
            print("╰─────────────────────────────────────────────────────────────╯")
            print()

            while True:
                try:
                    line = input("analyst> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                if not line:
                    continue
                if line.lower() in {"exit", "quit", ":q"}:
                    return

                # Send user message. Loop on function_call responses until plain text.
                response = chat.send_message(line)
                # Set True the moment a policy denial fires this turn; see
                # the hard-stop guard below — the SYSTEM_PROMPT already
                # tells the model to stop after a denial, but that's a
                # request, not a guarantee (observed live: Gemini
                # sometimes retries / explores anyway). Enforce it in
                # code instead of hoping the model complies.
                denied_this_turn = False

                while True:
                    parts = response.candidates[0].content.parts
                    function_calls = [p.function_call for p in parts if p.function_call]
                    if not function_calls:
                        # Plain text reply — print and break out to user prompt.
                        text = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
                        print(f"\nagent> {text}\n")
                        break

                    # Run each function_call against the MCP server.
                    fn_response_parts = []
                    for fc in function_calls:
                        name = fc.name
                        args = dict(fc.args or {})
                        # Normalize endpoint args Gemini sometimes mangles
                        # (duplicated scheme, wrong hostname). For this lab
                        # the canonical gateway is agentgateway:3000 over HTTP.
                        if "endpoint" in args:
                            agent_name = args.get("tool_name", "").split("_")[-1] if args.get("tool_name", "").startswith("lookup_") else "ip-reputation"
                            # tool_name 'lookup_ip' → agent 'ip-reputation' (manual map)
                            if agent_name == "ip":
                                agent_name = "ip-reputation"
                            args["endpoint"] = _canonical_endpoint(args["endpoint"], agent_name=agent_name)
                        # Belt-and-braces: even though the system prompt
                        # instructs Gemini to not pass placeholder args,
                        # strip any '_unused*' / 'a_unused*' keys the
                        # model still emits. They come from our
                        # _sanitize_schema's empty-object workaround.
                        if "arguments" in args and isinstance(args["arguments"], dict):
                            args["arguments"] = {
                                k: v for k, v in args["arguments"].items()
                                if not (k == "_unused" or k.startswith("a_unused"))
                            }
                        for placeholder_key in list(args.keys()):
                            if placeholder_key == "_unused" or placeholder_key.startswith("a_unused"):
                                args.pop(placeholder_key, None)

                        print(f"  [tool] {name}({args})")

                        # ── Hard stop after a policy denial ──────────
                        # Intercept EVERY further tool call this turn
                        # once a denial has fired — regardless of which
                        # tool the model is now trying (retry, broader
                        # discover_agents_via_dns, list_agent_tools,
                        # ...). No real MCP/SDK work, just a firm
                        # synthetic nudge, so exploration can't drag on.
                        if denied_this_turn:
                            result_text = json.dumps({
                                "error": (
                                    "STOP - a policy denial was already "
                                    "returned for this request in this "
                                    "turn. Do not retry the call, search "
                                    "for other agents, or call "
                                    "list_agent_tools. Immediately report "
                                    "the denial from your earlier tool "
                                    "result to the user and end your turn."
                                ),
                            })
                            print("  [guard] blocked further exploration after denial")
                            fn_response_parts.append(
                                types.Part.from_function_response(
                                    name=name,
                                    response={"content": result_text},
                                )
                            )
                            continue

                        # ── DNS-AID SDK caller-side policy guard ─────
                        # Layer 1 enforcement. See sdk_policy_check()
                        # above — the one and only SDK call site.
                        sdk_decision = None
                        sdk_status = "n/a"
                        if name == "call_agent_tool":
                            target_tool = args.get("tool_name")
                            sdk_decision = await sdk_policy_check(target_tool)
                            sdk_status = (
                                "ALLOWED by SDK caller guard"
                                if sdk_decision.allowed
                                else f"DENIED: {sdk_decision.reason}"
                            )
                            print(f"  [sdk-guard] tool={target_tool!r} → {sdk_status}")
                            if not sdk_decision.allowed:
                                result_text = json.dumps({
                                    "success": False,
                                    "blocked_by": "dns-aid SDK caller-side guard (Layer 1)",
                                    "reason": sdk_decision.reason,
                                    "policy_uri": _LAST_POLICY_URI,
                                    "violations": [
                                        {"rule": v.rule, "detail": v.detail}
                                        for v in sdk_decision.violations
                                    ],
                                    "telemetry": {
                                        "latency_ms": 0,
                                        "status": "policy_denied",
                                    },
                                })
                                fn_response_parts.append(
                                    types.Part.from_function_response(
                                        name=name,
                                        response={"content": result_text},
                                    )
                                )
                                # Print + skip the actual MCP call.
                                preview = result_text if len(result_text) < 400 else result_text[:400] + "..."
                                print(f"  [result] {preview}")
                                denied_this_turn = True
                                continue

                        if name not in mcp_tool_lookup:
                            result_text = json.dumps({"error": f"unknown tool: {name}"})
                        else:
                            try:
                                # Retry transparently on transient
                                # "Invocation failed" from call_agent_tool —
                                # the first invocation through a freshly-
                                # materialised xDS route can flake with an
                                # MCP-session race, ~17ms latency. One
                                # retry with a brief delay covers it.
                                async def _invoke():
                                    return await session.call_tool(name, args)

                                tool_result = await _invoke()
                                if name == "call_agent_tool":
                                    _peek = "".join(
                                        getattr(b, "text", "") for b in tool_result.content
                                    )
                                    if '"status": "error"' in _peek or '"success": false' in _peek:
                                        await asyncio.sleep(0.8)
                                        print("  [retry] transient invocation error, retrying once")
                                        tool_result = await _invoke()
                                pieces = []
                                for block in tool_result.content:
                                    if hasattr(block, "text"):
                                        pieces.append(block.text)
                                    else:
                                        pieces.append(str(block))
                                result_text = "\n".join(pieces) or "[empty]"
                                # If this was a discovery call, fetch the
                                # cap doc (S3) and check DNSSEC AD flag,
                                # then inline both into the response the
                                # model receives.
                                result_text = _enrich_with_cap_doc(
                                    name, result_text, SANDBOX_SLUG, ZONE,
                                )
                                # For call_agent_tool, inject structured
                                # audit fields the model MUST echo verbatim
                                # in its trust-chain reply. This eliminates
                                # the hallucination class where Gemini
                                # invents 'verified — signer xxx' from
                                # plausible-looking words in the cap doc.
                                if name == "call_agent_tool":
                                    try:
                                        result_obj = json.loads(result_text)
                                    except json.JSONDecodeError:
                                        result_obj = {"raw": result_text}
                                    target_tool = args.get("tool_name", "lookup_ip")
                                    audit = {
                                        "__jws_status": "not signed (cap doc unsigned)",
                                        "__signer_kid": None,
                                        "__invoked_via": f"http://agentgateway:3000/ip-reputation/mcp",
                                        "__sdk_guard": sdk_status,
                                    }
                                    if isinstance(result_obj, dict):
                                        result_obj.update(audit)
                                        result_text = json.dumps(result_obj, indent=2)
                            except Exception as exc:
                                result_text = json.dumps({"error": str(exc)})
                        # Print result so we see exactly what the model receives.
                        preview = result_text if len(result_text) < 400 else result_text[:400] + "..."
                        print(f"  [result] {preview}")

                        fn_response_parts.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"content": result_text},
                            )
                        )

                    # Send the tool outputs back; Gemini may call more tools or return text.
                    # Chat.send_message's message param is a bare Part (or
                    # list of Parts) — Union[str, File, Part, ...] — NOT a
                    # Content object. Confirmed live: wrapping in
                    # types.Content(role="tool", ...) raised ValueError
                    # ("got <class '...types.Content'>"); a plain list of
                    # Parts, exactly like the pre-migration code did, works.
                    response = chat.send_message(fn_response_parts)


if __name__ == "__main__":
    asyncio.run(main())
