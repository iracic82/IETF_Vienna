"""Vertex-Gemini agent for the IETF lab — no Strands, no LiteLLM.

Tool calling goes directly via vertexai.GenerativeModel which handles
MCP-style schemas natively. The Strands+LiteLLM+Vertex stack returns
UNEXPECTED_TOOL_CALL on every tool invocation, so we bypass it.

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
from typing import Any

# Vertex AI SDK
import vertexai
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

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

REQUIRED FLOW for IP queries:
  Step 1. Call discover_agents_via_dns with:
            domain   = "{SANDBOX_SLUG}.{ZONE}"
            protocol = "mcp"
            name     = "ip-reputation"
          The wrapper auto-fetches the cap_uri (the published contract on
          S3) and inlines `__cap_doc` into the result. Read it.
  Step 2. Read the agent record. Expect these fields:
            signature_status   ("verified" | "unsigned" | "missing")
            signer_kid          (string if signature_status=="verified", else null)
            dnssec_status       ("ad" | "no-ad" | "unsigned-zone" | "unknown")
            __cap_uri           the S3 URL the record points to
            __cap_doc           the parsed JSON contents of that URL
  Step 3. Call call_agent_tool with:
            tool_name = "lookup_ip"
            arguments = {{"ip": "<analyst's IP>"}}
  Step 4. Return ONLY what the federation actually replied, in this format:

            **Verdict:** <verdict from tool>
            **Confidence:** <confidence from tool>
            **Sources:** <sources from tool>
            **Trust chain (audit):**
            - SVCB record: _<name>._<proto>._agents.<domain>
            - DNSSEC: <ad-flag / not-enabled-in-lab>
            - JWS signature: <signer kid / "not signed (cap doc unsigned)">
            - Cap doc: <__cap_uri> (fetched, agent=<__cap_doc.agent>, version=<__cap_doc.version>)
            - Policy: <__cap_doc.policy_uri or "none">
            - Invoked via: <endpoint>

HONEST REPORTING — if a trust signal is missing, say so explicitly.
Examples:
  - If signature_status=="unsigned" → "JWS signature: not signed (cap doc unsigned)"
  - If signature_status=="verified" → "JWS signature: verified — signer <kid>"
  - If dnssec_status=="unsigned-zone" → "DNSSEC: not enabled in lab (parent zone unsigned)"
  - If dnssec_status=="ad" → "DNSSEC: validated (AD flag set on SVCB query)"
  - If __cap_doc is null → "Cap doc: <url> (fetch failed)"

If the federation says "unknown", REPORT unknown. If a tool fails, REPORT
the error verbatim.

Your sandbox subdomain is: {SANDBOX_SLUG}.{ZONE}

Be terse.
"""


# ── MCP → Vertex tool translation ─────────────────────────────────────
def mcp_tools_to_vertex(mcp_tools: list) -> Tool:
    """Convert MCP tool list into a single Vertex Tool with N FunctionDeclarations.

    MCP tool schema:  {name, description, inputSchema (JSON Schema)}
    Vertex schema:    FunctionDeclaration(name, description, parameters)
    """
    decls = []
    for t in mcp_tools:
        schema = t.inputSchema or {"type": "object", "properties": {}}
        # Vertex rejects schemas with empty `properties` on object type;
        # also doesn't like some JSON Schema features. Sanitize.
        schema = _sanitize_schema(schema)
        decls.append(
            FunctionDeclaration(
                name=t.name,
                description=(t.description or t.name)[:1024],
                parameters=schema,
            )
        )
    return Tool(function_declarations=decls)


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
# In this lab agentgateway is on the docker network at agentgateway:3000
# with PATH-based routing — each agent is reached at /<agent-name>/mcp.
# When Gemini emits a mangled or wrong endpoint, rewrite it to the
# canonical agent path so dns-aid's call_agent_tool hits a real route.
def _canonical_endpoint(raw: str | None, agent_name: str = "ip-reputation") -> str:
    # Gateway uses PATH routing /<agent>/mcp — dns-aid passes endpoint
    # verbatim, no /mcp suffix added, so we include the full path here.
    canonical = f"http://agentgateway:3000/{agent_name}/mcp"
    if not raw:
        return canonical
    if raw == canonical:
        return raw
    # Strip duplicate schemes.
    for prefix in ("httpshttps://", "https://https://", "http://http://"):
        if raw.startswith(prefix):
            raw = "http://" + raw[len(prefix):]
            break
    # If anything points at gw.<slug> or at agentgateway without the
    # /<agent>/mcp suffix, snap to canonical.
    if "gw." in raw and ".iracictechguru.com" in raw:
        return canonical
    if "agentgateway" in raw and not raw.endswith(f"/{agent_name}/mcp"):
        return canonical
    if raw.startswith("https://"):
        raw = "http://" + raw[len("https://"):]
    return raw


# ── Cap doc fetch + enrichment ─────────────────────────────────────────
# When the agent calls discover_agents_via_dns, we automatically GET the
# cap_uri (S3) and inline the parsed JSON into the result the model sees.
# This makes the S3 layer visibly part of the discovery flow — the model
# reads the actual contract before invoking.

_CAP_URL_RE = re.compile(r'https?://[^\s",}\]]+')


def _extract_cap_uris(result_text: str) -> list[str]:
    """Pull S3 cap doc URLs out of dns-aid discover's text output."""
    return list({
        url for url in _CAP_URL_RE.findall(result_text)
        if "/v1.json" in url or "cap" in url.lower()
    })


def _fetch_cap_doc(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"  [cap-fetch] FAILED {url}: {exc}")
        return None


def _enrich_with_cap_doc(name: str, result_text: str) -> str:
    """If the tool was discover_agents_via_dns, fetch any cap URLs and
    inline them as __cap_uri / __cap_doc fields the model can read."""
    if name != "discover_agents_via_dns":
        return result_text
    cap_uris = _extract_cap_uris(result_text)
    if not cap_uris:
        return result_text
    # Most labs have one cap_uri; if more, just fetch the first to keep
    # the response payload small.
    cap_uri = cap_uris[0]
    print(f"  [cap-fetch] GET {cap_uri}")
    cap_doc = _fetch_cap_doc(cap_uri)
    enrichment = {"__cap_uri": cap_uri, "__cap_doc": cap_doc}
    # Prepend enrichment as a JSON line so the model reliably parses it.
    return json.dumps(enrichment, indent=2) + "\n\n--- raw discover output ---\n" + result_text


# ── Async REPL ─────────────────────────────────────────────────────────
async def main() -> None:
    vertexai.init(project=PROJECT, location=LOCATION)

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

            model = GenerativeModel(
                model_name=MODEL_ID,
                system_instruction=SYSTEM_PROMPT,
                tools=[vertex_tools],
            )
            chat = model.start_chat()

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
                        print(f"  [tool] {name}({args})")
                        if name not in mcp_tool_lookup:
                            result_text = json.dumps({"error": f"unknown tool: {name}"})
                        else:
                            try:
                                tool_result = await session.call_tool(name, args)
                                pieces = []
                                for block in tool_result.content:
                                    if hasattr(block, "text"):
                                        pieces.append(block.text)
                                    else:
                                        pieces.append(str(block))
                                result_text = "\n".join(pieces) or "[empty]"
                                # If this was a discovery call, fetch the
                                # cap doc (S3) and inline it into the
                                # response the model receives. Makes the
                                # S3 layer a visible part of the flow.
                                result_text = _enrich_with_cap_doc(name, result_text)
                            except Exception as exc:
                                result_text = json.dumps({"error": str(exc)})
                        # Print result so we see exactly what the model receives.
                        preview = result_text if len(result_text) < 400 else result_text[:400] + "..."
                        print(f"  [result] {preview}")

                        fn_response_parts.append(
                            Part.from_function_response(
                                name=name,
                                response={"content": result_text},
                            )
                        )

                    # Send the tool outputs back; Gemini may call more tools or return text.
                    response = chat.send_message(fn_response_parts)


if __name__ == "__main__":
    asyncio.run(main())
