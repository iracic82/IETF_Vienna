/** Flow definitions for the DNS-AID Explorer.
 *  Each flow is a list of steps; each step lights up a node in the React
 *  Flow graph and populates the right detail panel.
 */

import type { Node, Edge } from "@xyflow/react";

export type FlowStepKind =
  | "tool_call"
  | "dns_query"
  | "dns_response"
  | "cap_fetch"
  | "jws_verify"
  | "xds_push"
  | "mcp_open"
  | "mcp_call"
  | "mcp_response"
  | "synthesis";

export type FlowStep = {
  id: string;
  label: string;
  nodeId: string;                 // which graph node lights up
  edgeFrom?: string;              // which edge animates in
  kind: FlowStepKind;
  detail: {
    title: string;
    rightPaneTabs: ("request" | "response" | "signature" | "trust")[];
    sampleRequest?: string;
    sampleResponse?: string;
    sampleSignature?: string;
    sampleTrust?: string;
  };
};

export type Flow = {
  id: string;
  title: string;
  category: "discovery" | "trust" | "governance";
  steps: FlowStep[];
  nodes: Node[];
  edges: Edge[];
};

// ──────────────────────────────────────────────────────────────────────
// IETF flow: ip-reputation discovery + invocation (10 steps)
//
// Reflects the current architecture:
//   - Zone: lab.ccdesanity.com (DNSSEC chain validates from root)
//   - Per-sandbox slug subdomain: <slug>.lab.ccdesanity.com
//   - Cap docs on S3: ietf-vienna-cap-docs.s3.amazonaws.com
//   - Model: Vertex Gemini 2.5 Pro (direct, no Strands wrapper)
//   - Translator: ghcr.io/iracic82/dns-aid-translator:0.3.0
//     polls Route 53 → emits Bind/Listener/Route/Backend via Envoy v3 ADS
//   - agentgateway: xDS-driven, ZERO static routes
//   - Path mode: POST /<agent>/mcp → fastmcp-<agent>:3000
//   - JWS: not signed in this lab (Route 53 TXT 255-char limit; honest report)
// ──────────────────────────────────────────────────────────────────────

// Layout: agent is the hub on the left at vertical center; the three
// horizontal swim-lanes (discovery / artifacts / enforcement) extend
// rightward. smoothstep edges + arrow markers give us clean orthogonal
// routing so no diagonal slices through other nodes.
//
//     y=0    Discovery:    agent → dns-aid → CoreDNS → Route 53
//     y=180  Artifacts:    agent → cap-s3            xDS-translator (polls R53)
//     y=360  Enforcement:  agent → sdk-guard → gateway → FastMCP
//
const IETF_NODES: Node[] = [
  { id: "agent",      position: { x:   0, y: 180 }, data: { label: "Vertex Gemini\nstrands-agent" }, type: "explorer" },
  { id: "dns-aid",    position: { x: 260, y:   0 }, data: { label: "dns-aid MCP" }, type: "explorer" },
  { id: "coredns",    position: { x: 520, y:   0 }, data: { label: "CoreDNS\nlocal resolver" }, type: "explorer" },
  { id: "route53",    position: { x: 780, y:   0 }, data: { label: "Route 53\nlab.ccdesanity.com (DNSSEC)" }, type: "explorer" },
  { id: "cap-s3",     position: { x: 260, y: 180 }, data: { label: "S3 cap doc\nietf-vienna-cap-docs" }, type: "explorer" },
  { id: "translator", position: { x: 780, y: 180 }, data: { label: "xDS translator\npolls Route 53" }, type: "explorer" },
  { id: "sdk-guard",  position: { x: 260, y: 360 }, data: { label: "dns-aid SDK guard\nLayer 1 (caller-side)" }, type: "explorer" },
  { id: "gateway",    position: { x: 520, y: 360 }, data: { label: "agentgateway\nxDS-driven, path-mode" }, type: "explorer" },
  { id: "fastmcp",    position: { x: 780, y: 360 }, data: { label: "FastMCP\nip-reputation" }, type: "explorer" },
];

const IETF_EDGES: Edge[] = [
  { id: "e1", source: "agent",      target: "dns-aid",    animated: true, label: "tool call" },
  { id: "e2", source: "dns-aid",    target: "coredns",    animated: true, label: "SVCB query" },
  { id: "e3", source: "coredns",    target: "route53",    animated: true, label: "auth" },
  { id: "e4", source: "agent",      target: "cap-s3",     animated: true, label: "fetch v1.json" },
  { id: "e5", source: "route53",    target: "translator", animated: true, label: "polled" },
  { id: "e6", source: "translator", target: "gateway",    animated: true, label: "xDS push" },
  { id: "e9", source: "agent",      target: "sdk-guard",  animated: true, label: "check policy" },
  { id: "e10", source: "sdk-guard", target: "cap-s3",     animated: true, label: "fetch policy.json" },
  { id: "e7", source: "agent",      target: "gateway",    animated: true, label: "MCP call" },
  { id: "e8", source: "gateway",    target: "fastmcp",    animated: true, label: "proxy" },
];

export const IETF_FLOW: Flow = {
  id: "ietf-discover-ip-reputation",
  title: "Discover & invoke ip-reputation",
  category: "discovery",
  nodes: IETF_NODES,
  edges: IETF_EDGES,
  steps: [
    {
      id: "1", label: "User asks", nodeId: "agent", kind: "tool_call",
      detail: {
        title: "Step 1 — Analyst asks the assistant",
        rightPaneTabs: ["request"],
        sampleRequest: 'analyst> Is 185.220.101.45 malicious?',
      },
    },
    {
      id: "2", label: "Discover tool call", nodeId: "agent", edgeFrom: "e1", kind: "tool_call",
      detail: {
        title: "Step 2 — Gemini selects discover_agents_via_dns",
        rightPaneTabs: ["request"],
        sampleRequest: 'tools/call {\n  "name": "discover_agents_via_dns",\n  "arguments": {\n    "domain": "${SLUG}.lab.ccdesanity.com",\n    "protocol": "mcp",\n    "name": "ip-reputation"\n  }\n}',
      },
    },
    {
      id: "3", label: "DNSSEC SVCB query", nodeId: "coredns", edgeFrom: "e2", kind: "dns_query",
      detail: {
        title: "Step 3 — dig +dnssec SVCB via CoreDNS → Route 53",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'dig +dnssec SVCB ip-reputation.${SLUG}.lab.ccdesanity.com',
        sampleResponse: ';; flags: qr rd ra ad ◄── DNSSEC validated\nip-reputation.${SLUG}.lab.ccdesanity.com. 30 IN SVCB\n  1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000\n\nTXT companion records (Route 53 demotes custom SvcParams to TXT):\n  "dnsaid_key65400=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json"\n  "dnsaid_key65403=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy.json"',
        sampleTrust: '. → com → ccdesanity.com → lab.ccdesanity.com\n✓ DS at .com TLD (KSK 39752)\n✓ DS at ccdesanity.com  (KSK 9396)\n✓ DNSKEY + RRSIG verified\n✓ AD flag returned by Cloudflare 1.1.1.1',
      },
    },
    {
      id: "4", label: "Cap doc fetch (S3)", nodeId: "cap-s3", edgeFrom: "e4", kind: "cap_fetch",
      detail: {
        title: "Step 4 — agent_vertex wrapper GETs cap_uri from S3",
        rightPaneTabs: ["request", "response"],
        sampleRequest: 'GET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json',
        sampleResponse: '{\n  "agent": "ip-reputation",\n  "version": "1.0.0",\n  "protocol": "mcp",\n  "transport": "streamable-http",\n  "mcp_server_card": "…/mcp-server-card.json",\n  "policy_uri": "…/policy.json",\n  "tools": [{"name": "lookup_ip", ...}]\n}\n\nReferenced via dnsaid_key65400 TXT record above ✓',
      },
    },
    {
      id: "5", label: "JWS check (honest)", nodeId: "cap-s3", kind: "jws_verify",
      detail: {
        title: "Step 5 — JWS signature check on cap doc",
        rightPaneTabs: ["signature", "trust"],
        sampleSignature: 'Lab publishes UNSIGNED (no JWS):\n  Reason: Route 53 demotes JWS to TXT; JWS token >255 chars exceeds\n  Route 53\'s per-string TXT limit. dns-aid v0.21 does not yet auto-\n  chunk TXT, so we publish without --sign.\n\nProduction federations would publish signed cap docs and verify here\nwith the published JWKS (k-ops-team-2026 etc.).',
        sampleTrust: 'Audit chain reports: "JWS signature: not signed (cap doc unsigned)"\nHONEST: integrity gap visible to the analyst, not silently glossed over.',
      },
    },
    {
      id: "6", label: "xDS push", nodeId: "translator", edgeFrom: "e5", kind: "xds_push",
      detail: {
        title: "Step 6 — Translator polls Route 53, pushes Route/Backend via xDS",
        rightPaneTabs: ["request", "response"],
        sampleRequest: 'Translator poll (every 5s):\n  dig SVCB ip-reputation.${SLUG}.lab.ccdesanity.com @coredns\n\nResult: SVCB record present (or absent → triggers route removal)',
        sampleResponse: 'Envoy v3 ADS DeltaDiscoveryResponse:\n  Bind     (port 3000)\n  Listener (dnsaid-discovered)\n  Route    (/ip-reputation/mcp exact → MCP backend)\n  Backend  (mcp wrapper)\n  Backend  (static → fastmcp-ip-reputation:3000)\n\nGateway materialises the new route in <1s after the push.',
      },
    },
    {
      id: "7", label: "MCP initialize", nodeId: "gateway", edgeFrom: "e7", kind: "mcp_open",
      detail: {
        title: "Step 7 — call_agent_tool opens MCP through agentgateway",
        rightPaneTabs: ["request"],
        sampleRequest: 'POST http://agentgateway:3000/ip-reputation/mcp\nContent-Type: application/json\nAccept: application/json, text/event-stream\nMCP-Protocol-Version: 2025-03-26\n\n{\n  "jsonrpc": "2.0",\n  "id": 1,\n  "method": "initialize",\n  "params": {"protocolVersion": "2025-03-26"}\n}',
      },
    },
    {
      id: "7b", label: "SDK guard check", nodeId: "sdk-guard", edgeFrom: "e9", kind: "jws_verify",
      detail: {
        title: "Step 7b — dns-aid SDK caller-side policy guard (Layer 1)",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'await check_target_policy(\n    policy_uri="https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy.json",\n    tool_name="lookup_ip",\n    method="tools/call",\n    caller_id="strands-agent-ietf-lab",\n)\n\nHelper: dns_aid.sdk.policy.guard.check_target_policy (dns-aid ≥0.21.3)\nWrapped in sdk_policy_check() — agent_vertex.py',
        sampleResponse: 'PolicyResult(\n  allowed=True,\n  violations=[],\n  reason="allowed",\n)\n\n[sdk-guard] tool=\'lookup_ip\' → ALLOWED by SDK caller guard\n\n(With POLICY_OVERRIDE → policy-strict.json: allowed=False,\n  violations=[{rule:"cel:tool-deny-all",\n              detail:"STRICT policy: \'lookup_ip\' is BLOCKED"}])',
        sampleTrust: 'Same PolicyEvaluator used by:\n  Layer 1 — caller SDK (this step)\n  Layer 2 — target ASGI middleware\n  Layer 3 — runtime gateway CEL\n  Layer 0 — bind-aid RPZ (IETF2)\n\nOne policy.json drives all four layers — published in DNS, evaluated\nwherever enforcement makes sense for the threat model.',
      },
    },
    {
      id: "8", label: "tools/call lookup_ip", nodeId: "fastmcp", edgeFrom: "e8", kind: "mcp_call",
      detail: {
        title: "Step 8 — Invoke lookup_ip on fastmcp-ip-reputation",
        rightPaneTabs: ["request"],
        sampleRequest: '{\n  "jsonrpc": "2.0",\n  "id": 2,\n  "method": "tools/call",\n  "params": {\n    "name": "lookup_ip",\n    "arguments": {"ip": "185.220.101.45"}\n  }\n}',
      },
    },
    {
      id: "9", label: "Verdict", nodeId: "fastmcp", kind: "mcp_response",
      detail: {
        title: "Step 9 — Federation returns verdict from real lookup DB",
        rightPaneTabs: ["response"],
        sampleResponse: '{\n  "ip": "185.220.101.45",\n  "verdict": "malicious",\n  "confidence": 0.95,\n  "sources": ["tor-exit-list", "abuse.ch"],\n  "tags": ["tor"]\n}',
      },
    },
    {
      id: "10", label: "Synthesis + audit chain", nodeId: "agent", kind: "synthesis",
      detail: {
        title: "Step 10 — Agent synthesizes answer with honest audit trail",
        rightPaneTabs: ["response"],
        sampleResponse: 'agent> **Verdict:** malicious\n       **Confidence:** 0.95\n       **Sources:** tor-exit-list, abuse.ch\n       **Trust chain (audit):**\n       - SVCB record: ip-reputation.${SLUG}.lab.ccdesanity.com\n       - DNSSEC: validated (AD flag set on SVCB query against 1.1.1.1)\n       - JWS signature: not signed (cap doc unsigned)\n       - Cap doc: https://ietf-vienna-cap-docs.s3.amazonaws.com/...v1.json (fetched, agent=ip-reputation, version=1.0.0)\n       - Policy: https://ietf-vienna-cap-docs.s3.amazonaws.com/...policy.json\n       - Invoked via: http://agentgateway:3000/ip-reputation/mcp',
      },
    },
  ],
};

// ──────────────────────────────────────────────────────────────────────
// IETF denied flow: same architecture, but POLICY_OVERRIDE points the
// SDK at policy-strict.json so step 7b denies and the call never leaves
// the agent. Mirrors C3 Bonus 3 — students can switch between this and
// the happy path to see ALLOWED vs DENIED side-by-side.
// ──────────────────────────────────────────────────────────────────────

export const IETF_DENIED_FLOW: Flow = {
  id: "ietf-discover-deny-strict",
  title: "Discover & deny (strict policy)",
  category: "trust",
  nodes: IETF_NODES,
  edges: IETF_EDGES,
  steps: [
    {
      id: "1", label: "User asks", nodeId: "agent", kind: "tool_call",
      detail: {
        title: "Step 1 — Analyst asks the assistant (POLICY_OVERRIDE active)",
        rightPaneTabs: ["request"],
        sampleRequest: 'analyst> Is 185.220.101.45 malicious?\n\n# Environment for this run:\n#   POLICY_OVERRIDE=https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy-strict.json\n# The agent will still discover via DNS, fetch the cap doc, etc.\n# Only the SDK caller-side guard sees the strict policy.',
      },
    },
    {
      id: "2", label: "Discover tool call", nodeId: "agent", edgeFrom: "e1", kind: "tool_call",
      detail: {
        title: "Step 2 — Gemini selects discover_agents_via_dns",
        rightPaneTabs: ["request"],
        sampleRequest: 'tools/call {\n  "name": "discover_agents_via_dns",\n  "arguments": {\n    "domain": "${SLUG}.lab.ccdesanity.com",\n    "protocol": "mcp",\n    "name": "ip-reputation"\n  }\n}',
      },
    },
    {
      id: "3", label: "DNSSEC SVCB query", nodeId: "coredns", edgeFrom: "e2", kind: "dns_query",
      detail: {
        title: "Step 3 — DNS resolution (succeeds — discovery isn't gated by policy)",
        rightPaneTabs: ["request", "response"],
        sampleRequest: 'dig +dnssec SVCB ip-reputation.${SLUG}.lab.ccdesanity.com',
        sampleResponse: ';; flags: qr rd ra ad ◄── DNSSEC validated\nip-reputation.${SLUG}.lab.ccdesanity.com. 30 IN SVCB\n  1 fastmcp-ip-reputation. mandatory=alpn,port alpn="mcp" port=3000\n\nNote: discovery succeeds regardless of policy. The strict policy only\nfires at Layer 1 (SDK caller guard) when the agent is about to invoke.',
      },
    },
    {
      id: "4", label: "Cap doc fetch", nodeId: "cap-s3", edgeFrom: "e4", kind: "cap_fetch",
      detail: {
        title: "Step 4 — Cap doc fetched (still v1.json, not the strict policy)",
        rightPaneTabs: ["request"],
        sampleRequest: 'GET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json\n\nThis still returns the cap doc envelope. The STRICT policy lives at a\ndifferent S3 URL (policy-strict.json) — fetched only by the SDK guard\nin step 7b, because POLICY_OVERRIDE is set on the agent process.',
      },
    },
    {
      id: "7", label: "MCP initialize", nodeId: "gateway", edgeFrom: "e7", kind: "mcp_open",
      detail: {
        title: "Step 7 — MCP session opens (still happens — gateway has the route)",
        rightPaneTabs: ["request"],
        sampleRequest: 'POST http://agentgateway:3000/ip-reputation/mcp\n{"method":"initialize", ...}\n\nThe initialize handshake completes — the gateway routes it through\nbecause the gateway itself has no policy enforcement wired here.\n(Layer 3 enforcement is the next IETF workshop.)',
      },
    },
    {
      id: "7b", label: "SDK guard — DENIED", nodeId: "sdk-guard", edgeFrom: "e9", kind: "jws_verify",
      detail: {
        title: "Step 7b — SDK caller-side guard fires → DENIED (no network call)",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'await check_target_policy(\n    policy_uri="…/policy-strict.json",   # via POLICY_OVERRIDE\n    tool_name="lookup_ip",\n    method="tools/call",\n    caller_id="strands-agent-ietf-lab",\n)',
        sampleResponse: 'PolicyResult(\n  allowed=False,\n  violations=[\n    PolicyViolation(\n      rule="cel:tool-deny-all",\n      detail="STRICT policy: \'lookup_ip\' is BLOCKED. Only initialize/tools/list permitted."\n    )\n  ],\n)\n\n[sdk-guard] tool=\'lookup_ip\' → DENIED\n[result] {"success": false, "blocked_by": "dns-aid SDK caller-side guard (Layer 1)", "telemetry": {"latency_ms": 0, "status": "policy_denied"}}',
        sampleTrust: 'STRICT policy CEL rule (request must be TRUE to be allowed):\n  request.tool_name == null  // only meta-methods like tools/list\n\nFor tool_name="lookup_ip" the expression evaluates FALSE → deny effect\nfires → PolicyResult.allowed=False.\n\nlatency_ms=0 — the network call was never made. The SDK guard\nrefused the invocation before the bytes left the process.',
      },
    },
    {
      id: "10", label: "Model refuses gracefully", nodeId: "agent", kind: "synthesis",
      detail: {
        title: "Step 10 — Gemini sees the structured denial and refuses cleanly",
        rightPaneTabs: ["response"],
        sampleResponse: 'agent> The lookup for 185.220.101.45 was blocked by a security policy.\n       I cannot provide a verdict.\n\n       **Reason:** The tool call was denied by the agent\'s security\n       policy. The policy URI is\n       https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy-strict.json\n       and the reason given was: "STRICT policy: \'lookup_ip\' is BLOCKED.\n       Only initialize/tools/list permitted."\n\nNo verdict invented. No retry storm. No hallucinated source. The model\nreceives a structured PolicyResult and surfaces it honestly.',
      },
    },
  ],
};

// ──────────────────────────────────────────────────────────────────────
// "Where policy is enforced" overview: a non-animated, content-first
// flow that walks through the four DNS-AID enforcement layers, lighting
// up the relevant node for each layer so students see where it lives in
// the topology. L0 (resolver/bind-aid) and L3 (gateway CEL) are
// flagged as IETF2-future since this lab only exercises L1 and L2.
// ──────────────────────────────────────────────────────────────────────

export const IETF_LAYERS_OVERVIEW: Flow = {
  id: "ietf-layers-overview",
  title: "Where policy is enforced (4 layers)",
  category: "governance",
  nodes: IETF_NODES,
  edges: IETF_EDGES,
  steps: [
    {
      id: "L0", label: "Layer 0 — DNS resolver (bind-aid)", nodeId: "coredns", kind: "dns_query",
      detail: {
        title: "Layer 0 — DNS resolver enforcement (bind-aid RPZ)",
        rightPaneTabs: ["request", "trust"],
        sampleRequest: '# Compiled from the same policy.json into RPZ rules:\nip-reputation.<zone>  CNAME  rpz-passthru.  ; allow\nbilling.<zone>        CNAME  .              ; NXDOMAIN for non-permitted callers\n\nA DNSSEC-aware resolver with bind-aid loaded answers NXDOMAIN to\ncallers whose source IP / domain doesn\'t match the policy — the\nrequest never even leaves the caller\'s network namespace.',
        sampleTrust: 'IN THIS LAB: NOT EXERCISED.\nCoreDNS here is a plain DNSSEC-validating forwarder; no RPZ loaded.\n\nIETF2 (90-min advanced workshop, planned): BIND + bind-aid integration\nthat compiles policy.json → RPZ → resolver refuses to even reveal\nwhere the target lives for unauthorised callers.',
      },
    },
    {
      id: "L1", label: "Layer 1 — Caller SDK", nodeId: "sdk-guard", kind: "jws_verify",
      detail: {
        title: "Layer 1 — dns-aid SDK caller-side guard",
        rightPaneTabs: ["request", "trust"],
        sampleRequest: 'from dns_aid.sdk.policy.guard import check_target_policy\n\nresult = await check_target_policy(\n    policy_uri=cap_doc.policy_uri,\n    tool_name="lookup_ip",\n    method="tools/call",\n    caller_id="my-agent",\n)\nif result.denied:\n    return refuse(result.reason)',
        sampleTrust: 'IN THIS LAB: ✓ EXERCISED.\nCalled from agent_vertex.py before every tools/call. Default\npolicy.json allows lookup_ip; POLICY_OVERRIDE → policy-strict.json\ndenies (C3 Bonus 3).\n\nSAME PolicyEvaluator runs in all four layers — one document, four\nenforcement points.',
      },
    },
    {
      id: "L2", label: "Layer 2 — Target ASGI middleware", nodeId: "fastmcp", kind: "synthesis",
      detail: {
        title: "Layer 2 — target-side ASGI middleware",
        rightPaneTabs: ["request", "trust"],
        sampleRequest: '# In the agent SERVER (fastmcp), every incoming request runs:\nfrom dns_aid.sdk.policy.middleware import PolicyMiddleware\n\napp.add_middleware(PolicyMiddleware, policy_uri="…/policy.json")\n\n# Same PolicyEvaluator, same PolicyContext shape — mandatory layer,\n# regardless of whether the caller cooperated.',
        sampleTrust: 'IN THIS LAB: ❌ NOT WIRED.\nThe fastmcp container in this lab serves raw — no PolicyMiddleware\nattached. To keep the lab focused on caller-side enforcement.\n\nIn a production federation: L2 is the MANDATORY layer. Even if a\ncaller skipped L1 or lied about identity, the target re-checks the\nSAME policy.json and denies.',
      },
    },
    {
      id: "L3", label: "Layer 3 — Runtime gateway", nodeId: "gateway", kind: "mcp_open",
      detail: {
        title: "Layer 3 — runtime sidecar gateway (CEL on the proxy)",
        rightPaneTabs: ["request", "trust"],
        sampleRequest: '# agentgateway TrafficPolicySpec could carry CEL expressions:\nspec.policy.cel.expression = "request.headers[\'authorization\'] != \'\'"\nspec.policy.cel.deny_message = "auth required"\n\n# Independent of caller SDK, independent of target server.\n# Routing, CORS, observability, future authn/authz.',
        sampleTrust: 'IN THIS LAB: ☑ PARTIAL.\nagentgateway runs and routes traffic + carries our CORS policy, but\npolicy CEL on the gateway is an IETF2 add.\n\nThe FOUR-LAYER PROMISE: one signed PolicyDocument → resolver +\ncaller + target + gateway all read the same doc, all evaluate the\nsame rules, all refuse for the same reason. No single trust anchor.',
      },
    },
  ],
};

// IETF2 placeholder flows removed — those belong to the future 90-min
// IETF2 workshop. The current Vienna lab surfaces:
//   1. happy-path discover-and-invoke story (IETF_FLOW)
//   2. policy denial via POLICY_OVERRIDE (IETF_DENIED_FLOW)
//   3. 4-layer enforcement model overview (IETF_LAYERS_OVERVIEW)

export const ALL_FLOWS: Flow[] = [IETF_FLOW, IETF_DENIED_FLOW, IETF_LAYERS_OVERVIEW];
