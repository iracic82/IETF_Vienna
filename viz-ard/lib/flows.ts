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
  outcome?: "denied";            // renders the active node/edge in red
                                  // (a policy block, not a success)
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
// IETF flow: ip-reputation discovery + invocation (13 steps)
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
  // Route the MCP-call edge out of the agent's BOTTOM and into the
  // gateway's TOP so it doesn't run along y=180 through the S3 cap-doc
  // node (which would falsely read as "the invocation goes via the cap doc").
  { id: "e7", source: "agent",      target: "gateway",    animated: true, label: "MCP call", sourceHandle: "b", targetHandle: "t" },
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
      id: "2", label: "Discover tool call", nodeId: "dns-aid", edgeFrom: "e1", kind: "tool_call",
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
      id: "3b", label: "Authoritative answer", nodeId: "route53", edgeFrom: "e3", kind: "dns_query",
      detail: {
        title: "Step 3b — CoreDNS recurses to Route 53 (authoritative, DNSSEC-signed)",
        rightPaneTabs: ["response", "trust"],
        sampleResponse: 'CoreDNS is a local VALIDATING resolver — it doesn\'t own the\nrecord, it recurses to the authoritative zone. Route 53 hosts\nlab.ccdesanity.com and returns the signed SVCB + RRSIG:\n\n  ip-reputation.${SLUG}.lab.ccdesanity.com.  30  IN  SVCB  1 fastmcp-ip-reputation. …\n  ip-reputation.${SLUG}.lab.ccdesanity.com.  30  IN  RRSIG SVCB … (Route 53 KSK/ZSK)\n\nCoreDNS caches the answer for the TTL (30s). Route 53 is the\nSOURCE OF TRUTH — the DNSSEC chain terminates in its signed zone.',
        sampleTrust: 'WHY ROUTE 53 MATTERS HERE:\n  - It is the authoritative, DNSSEC-signed origin of the record.\n    The AD flag the resolver set is only trustworthy because the\n    chain validates down to Route 53\'s signed zone.\n  - After this resolution the answer is cached; Route 53 is NOT\n    re-queried for the rest of the invocation (the agent already\n    has the endpoint + cap_uri/policy_uri).\n  - Route 53 is queried AGAIN later — but by the xDS translator\n    (Step 6), which polls it every 5s to keep gateway routes in\n    sync. Publisher-side, not caller-side.',
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
      id: "6b", label: "Route materialises", nodeId: "gateway", edgeFrom: "e6", kind: "xds_push",
      detail: {
        title: "Step 6b — the xDS push lands: the route appears on agentgateway",
        rightPaneTabs: ["response"],
        sampleResponse: 'agentgateway had ZERO routes at boot. The translator\'s ADS push\nnow installs, with no human editing the gateway config:\n  Listener  dnsaid-discovered\n  Route     = /ip-reputation/mcp   (exact match)\n  Backend   → fastmcp-ip-reputation:3000\n\nThe route exists purely because a DNS SVCB record exists. Delete\nthe record and — one TTL later — the translator pushes an empty\nsnapshot and this route vanishes. THIS edge is "DNS as the runtime\ncontrol plane": Route 53 (Step 3b) → translator → gateway.',
      },
    },
    {
      id: "7", label: "SDK guard check", nodeId: "sdk-guard", edgeFrom: "e9", kind: "jws_verify",
      detail: {
        title: "Step 7 — dns-aid SDK caller-side policy guard runs FIRST (Layer 1)",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'await check_target_policy(\n    policy_uri="https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/policy.json",\n    tool_name="lookup_ip",\n    method="tools/call",\n    caller_id="strands-agent-ietf-lab",\n)\n\n# agent_vertex.py runs this guard BEFORE call_agent_tool() invokes\n# anything. Only allowed=True lets the MCP call (next step) go out.\nHelper: dns_aid.sdk.policy.guard.check_target_policy (dns-aid ≥0.21.3)',
        sampleResponse: 'PolicyResult(\n  allowed=True,\n  violations=[],\n  reason="allowed",\n)\n\n[sdk-guard] tool=\'lookup_ip\' → ALLOWED by SDK caller guard\n\n(With POLICY_OVERRIDE → policy-strict.json this returns allowed=False\n and the MCP call never happens — see the "Discover & deny" flow.)',
        sampleTrust: 'Same PolicyEvaluator used by:\n  Layer 1 — caller SDK (this step)\n  Layer 2 — target ASGI middleware\n  Layer 3 — runtime gateway CEL\n  Layer 0 — bind-aid RPZ (IETF2)\n\nOne policy.json drives all four layers — published in DNS, evaluated\nwherever enforcement makes sense for the threat model.',
      },
    },
    {
      id: "8", label: "MCP initialize", nodeId: "gateway", edgeFrom: "e7", kind: "mcp_open",
      detail: {
        title: "Step 8 — guard allowed → call_agent_tool opens MCP through agentgateway",
        rightPaneTabs: ["request"],
        sampleRequest: 'POST http://agentgateway:3000/ip-reputation/mcp\nContent-Type: application/json\nAccept: application/json, text/event-stream\nMCP-Protocol-Version: 2025-03-26\n\n{\n  "jsonrpc": "2.0",\n  "id": 1,\n  "method": "initialize",\n  "params": {"protocolVersion": "2025-03-26"}\n}',
      },
    },
    {
      id: "9", label: "tools/call lookup_ip", nodeId: "fastmcp", edgeFrom: "e8", kind: "mcp_call",
      detail: {
        title: "Step 9 — Invoke lookup_ip on fastmcp-ip-reputation",
        rightPaneTabs: ["request"],
        sampleRequest: '{\n  "jsonrpc": "2.0",\n  "id": 2,\n  "method": "tools/call",\n  "params": {\n    "name": "lookup_ip",\n    "arguments": {"ip": "185.220.101.45"}\n  }\n}',
      },
    },
    {
      id: "10", label: "Verdict", nodeId: "fastmcp", kind: "mcp_response",
      detail: {
        title: "Step 10 — Federation returns verdict from real lookup DB",
        rightPaneTabs: ["response"],
        sampleResponse: '{\n  "ip": "185.220.101.45",\n  "verdict": "malicious",\n  "confidence": 0.95,\n  "sources": ["tor-exit-list", "abuse.ch"],\n  "tags": ["tor"]\n}',
      },
    },
    {
      id: "11", label: "Synthesis + audit chain", nodeId: "agent", kind: "synthesis",
      detail: {
        title: "Step 11 — Agent synthesizes answer with honest audit trail",
        rightPaneTabs: ["response"],
        sampleResponse: 'agent> **Verdict:** malicious\n       **Confidence:** 0.95\n       **Sources:** tor-exit-list, abuse.ch\n       **Trust chain (audit):**\n       - SVCB record: ip-reputation.${SLUG}.lab.ccdesanity.com\n       - DNSSEC: validated (AD flag set on SVCB query against 1.1.1.1)\n       - JWS signature: not signed (cap doc unsigned)\n       - SDK guard: ALLOWED by SDK caller guard (Layer 1)\n       - Cap doc: https://ietf-vienna-cap-docs.s3.amazonaws.com/...v1.json (fetched, agent=ip-reputation, version=1.0.0)\n       - Policy: https://ietf-vienna-cap-docs.s3.amazonaws.com/...policy.json\n       - Invoked via: http://agentgateway:3000/ip-reputation/mcp',
      },
    },
  ],
};

// ──────────────────────────────────────────────────────────────────────
// IETF denied flow: same architecture, but POLICY_OVERRIDE points the
// SDK at policy-strict.json so step 5 denies and the call never leaves
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
      id: "2", label: "Discover tool call", nodeId: "dns-aid", edgeFrom: "e1", kind: "tool_call",
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
        sampleRequest: 'GET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/v1.json\n\nThis still returns the cap doc envelope. The STRICT policy lives at a\ndifferent S3 URL (policy-strict.json) — fetched only by the SDK guard\nin step 5, because POLICY_OVERRIDE is set on the agent process.',
      },
    },
    {
      id: "5", label: "SDK guard — DENIED", nodeId: "sdk-guard", edgeFrom: "e9", kind: "jws_verify", outcome: "denied",
      detail: {
        title: "Step 5 — SDK caller-side guard DENIES the lookup_ip call (Layer 1)",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'await check_target_policy(\n    policy_uri="…/policy-strict.json",   # via POLICY_OVERRIDE\n    tool_name="lookup_ip",\n    method="tools/call",\n    caller_id="strands-agent-ietf-lab",\n)\n\n# This guard runs BEFORE call_agent_tool(). Because it denies, the\n# agent never opens the MCP session — nothing reaches agentgateway\n# or FastMCP (they stay dark, to the right).',
        sampleResponse: 'PolicyResult(\n  allowed=False,\n  violations=[\n    PolicyViolation(\n      rule="cel:tool-deny-all",\n      detail="STRICT policy: \'lookup_ip\' is BLOCKED. Only initialize/tools/list permitted."\n    )\n  ],\n)\n\n[sdk-guard] tool=\'lookup_ip\' → DENIED\n[result] {"success": false, "blocked_by": "dns-aid SDK caller-side guard (Layer 1)", "telemetry": {"latency_ms": 0, "status": "policy_denied"}}',
        sampleTrust: 'STRICT policy CEL rule (request must be TRUE to be allowed):\n  request.tool_name == null  // only meta-methods like tools/list\n\nFor tool_name="lookup_ip" the expression evaluates FALSE → deny effect\nfires → PolicyResult.allowed=False.\n\nlatency_ms=0 — the network call was NEVER made. The guard refused the\ninvocation before any bytes left the process. This is why agentgateway\nand FastMCP never light up in this flow — the call died at Layer 1.',
      },
    },
    {
      id: "6", label: "Model refuses gracefully", nodeId: "agent", kind: "synthesis",
      detail: {
        title: "Step 6 — Gemini sees the structured denial and refuses cleanly",
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

// ──────────────────────────────────────────────────────────────────────
// IETF ARD flow: alternative discovery via the HTTPS ai-catalog.json
// path defined by https://agenticresourcediscovery.org/spec/
//
// Same agent backend, different discovery transport. The Lambda
// (ard-search) fetches the global ai-catalog.json from S3, applies a
// text + filter query (ARD §7.1), returns matching entries. The
// agent picks one and proceeds with the SAME invocation path
// (sdk-guard → gateway → fastmcp) as the DNS-AID flow — pedagogical
// point: discovery is a transport choice, runtime is shared.
// ──────────────────────────────────────────────────────────────────────

const ARD_NODES: Node[] = [
  ...IETF_NODES,
  { id: "ard-search",  position: { x: 1040, y: 180 }, data: { label: "ARD search Lambda\nPOST /search (optional)" }, type: "explorer" },
  { id: "ard-catalog", position: { x: 1040, y:   0 }, data: { label: "ARD catalog on S3\n/.well-known/ai-catalog.json" }, type: "explorer" },
];

const ARD_EDGES: Edge[] = [
  // DNS-AID base plane is shown faded — students see the contrast.
  ...IETF_EDGES,
  // Native dns-aid 0.26.2 ARD path (primary discovery route):
  //   agent → dns-aid MCP (existing e1, "tool call")
  //   dns-aid → CoreDNS  (existing e2, now doubles as SVCB pointer lookup)
  //   dns-aid MCP directly fetches the catalog from S3 (NEW ard1)
  //   catalog entries reference the same cap-s3 docs (NEW ard2)
  { id: "ard1", source: "dns-aid",     target: "ard-catalog", animated: true, label: "fetch /.well-known/ai-catalog.json" },
  { id: "ard2", source: "ard-catalog", target: "cap-s3",      animated: true, label: "entry.url → mcp-server-card.json" },
  // Optional manual /search bonus path — still real, students can curl it:
  { id: "ard3", source: "agent",       target: "ard-search",  animated: true, label: "optional: /search (curl)" },
  { id: "ard4", source: "ard-search",  target: "ard-catalog", animated: true, label: "reads same catalog" },
];

export const IETF_ARD_FLOW: Flow = {
  id: "ietf-ard-discover-http",
  title: "Discover via ARD (HTTPS catalog)",
  category: "discovery",
  nodes: ARD_NODES,
  edges: ARD_EDGES,
  steps: [
    {
      id: "1", label: "User asks", nodeId: "agent", kind: "tool_call",
      detail: {
        title: "Step 1 — Analyst asks the assistant (ARD discovery path)",
        rightPaneTabs: ["request"],
        sampleRequest: 'analyst> Is 185.220.101.45 malicious?\n\n# Same question as the DNS-AID flow.\n# This time the agent will discover via ARD instead of SVCB.',
      },
    },
    {
      id: "2", label: "Native ARD via dns-aid MCP", nodeId: "dns-aid", edgeFrom: "e1", kind: "tool_call",
      detail: {
        title: "Step 2 — Agent calls discover_agents_via_dns (use_http_index + trust_dnssec_pointers)",
        rightPaneTabs: ["request"],
        sampleRequest: '// SAME MCP tool the DNS-AID flow used — just two flags.\n// dns-aid auto-detects the ARD catalog pointer and fetches the\n// catalog natively. No new agent code needed.\n\ntools/call {\n  "name": "discover_agents_via_dns",\n  "arguments": {\n    "domain":                "${SLUG}.lab.ccdesanity.com",\n    "protocol":              "mcp",\n    "use_http_index":        true,   // ← ARD / HTTP-index path\n    "trust_dnssec_pointers": true    // ← follow the OFF-DOMAIN S3 pointer\n                                     //    because it is DNSSEC-signed.\n                                     //    Required since dns-aid 0.26.4:\n                                     //    off-domain pointers are refused\n                                     //    unless authenticated (JWS or DNSSEC).\n  }\n}\n\n// dns-aid MCP server (dns-aid-mcp container) receives the call,\n// then resolves the DNSSEC-signed catalog pointer over DNS (next step).',
      },
    },
    {
      id: "3", label: "Resolve SVCB catalog pointer", nodeId: "coredns", edgeFrom: "e2", kind: "dns_query",
      detail: {
        title: "Step 3 — dns-aid resolves _catalog._agents.<domain> SVCB pointer",
        rightPaneTabs: ["request", "response"],
        sampleRequest: '// dns-aid 0.26 tries both dual-label pointers per spec:\n//   _catalog._agents.<domain>   (ARD §6.1)\n//   _index._agents.<domain>     (DNS-AID draft-02 §3.2)\n// _catalog wins if both are present.\n\ndig +short SVCB _catalog._agents.${SLUG}.lab.ccdesanity.com @coredns',
        sampleResponse: '1 ietf-vienna-cap-docs.s3.amazonaws.com. alpn="h2" port="443"\n\n// Pointer says: fetch the catalog from S3.\n// dns-aid builds the well-known URL:\n//   https://ietf-vienna-cap-docs.s3.amazonaws.com/.well-known/ai-catalog.json\n// Published by the student via:\n//   dns-aid index publish-catalog ${SLUG}.lab.ccdesanity.com ietf-vienna-cap-docs.s3.amazonaws.com',
      },
    },
    {
      id: "3b", label: "Pointer is authoritative", nodeId: "route53", edgeFrom: "e3", kind: "dns_query",
      detail: {
        title: "Step 3b — the _catalog._agents pointer is an authoritative, signed Route 53 record",
        rightPaneTabs: ["response", "trust"],
        sampleResponse: 'CoreDNS doesn\'t own the pointer — it recurses to Route 53, the\nauthoritative zone for lab.ccdesanity.com. The pointer is a real,\nDNSSEC-signed SVCB record published by:\n\n  dns-aid index publish-catalog ${SLUG}.lab.ccdesanity.com \\\n      ietf-vienna-cap-docs.s3.amazonaws.com\n\nSo "where the ARD catalog lives" is itself signed DNS — the HTTPS\ncatalog is discovered through the SAME trust root as a bare SVCB.',
        sampleTrust: 'The ARD catalog host is only as trustworthy as the DNS pointer\nthat advertises it. Because that pointer is DNSSEC-signed in\nRoute 53, an attacker can\'t redirect discovery to a rogue catalog\nwithout breaking the chain.\n\nSame authoritative source (Route 53) as the DNS-AID flow — just a\ndifferent record: _catalog._agents.<domain> (the pointer) vs the\nflat <agent>.<domain> SVCB (the agent itself).',
      },
    },
    {
      id: "4", label: "Fetch ai-catalog.json + dereference cards", nodeId: "ard-catalog", edgeFrom: "ard1", kind: "cap_fetch",
      detail: {
        title: "Step 4 — dns-aid fetches the catalog, then dereferences each entry's card",
        rightPaneTabs: ["response", "trust"],
        sampleResponse: '// The NATIVE path fetches the RAW shared ai-catalog.json from S3\n// (NOT the Lambda /search envelope). Shape = {specVersion, host,\n// entries[]}, and identities are GLOBAL (lab.ccdesanity.com), because\n// every student\'s pointer targets the SAME shared catalog file.\n{\n  "specVersion": "1.0",\n  "host": {\n    "displayName":  "CCDeSanity Threat-Intel Federation (IETF Vienna ARD lab)",\n    "identifier":   "did:web:lab.ccdesanity.com",\n    "trustManifest": { "identity": "did:web:lab.ccdesanity.com", "identityType": "did" }\n  },\n  "entries": [\n    {\n      "identifier":  "urn:air:lab.ccdesanity.com:agent:ip-reputation",\n      "displayName": "IP Reputation",\n      "type":        "application/mcp-server-card+json",\n      "url":         "https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/mcp-server-card.json",\n      "version":     "1.0.0",\n      "trustManifest": {\n        "identity":     "spiffe://lab.ccdesanity.com/agents/ip-reputation",\n        "identityType": "spiffe",\n        "attestations": [\n          {"type":"publisher-identity"},\n          {"type":"SOC2-Type2",    "digest":"sha256:bc46d2..."},\n          {"type":"ISO27001-2022", "digest":"sha256:08cb86..."},\n          {"type":"GDPR-DPA"}\n        ]\n      },\n      "metadata": {\n        "io.dnsaid.capUri":    ".../ip-reputation/v1.json",\n        "io.dnsaid.policyUri": ".../ip-reputation/policy.json"\n      }\n    }\n    // + 7 more entries: asn-info, cve-lookup, domain-age, file-hash,\n    //   passive-dns, threat-feed, url-scanner (all urn:air:lab.ccdesanity.com:…)\n  ]\n}\n\n// The per-student view (slug-rewritten URNs + score ranking) is the\n// OPTIONAL ard-search Lambda path (POST /students/<slug>/search) —\n// same agents, re-anchored under spiffe://<slug>.lab.ccdesanity.com.',
        sampleTrust: 'WHAT THE TRUSTMANIFEST GIVES YOU (native path → global identities):\n\n  identity (SPIFFE)\n    → spiffe://lab.ccdesanity.com/agents/ip-reputation\n    → cryptographically binds this workload to the publisher\n      domain, per ai-catalog.io §Trust Manifest\n\n  4 attestations\n    → publisher-identity  — JWT proving the did:web publisher\n    → SOC2-Type2          — sha256-pinned audit PDF\n    → ISO27001-2022       — sha256-pinned cert PDF\n    → GDPR-DPA            — data processing addendum\n\n  provenance.publishedFrom\n    → source: github.com/iracic82/IETF_Vienna (sha256-pinned)\n    → registry: ietf-vienna-cap-docs S3 bucket\n    → consumers can trace the build → publish chain end to end\n\n  trustSchema.urn:trust:lab.ccdesanity.com:federation-v1\n    → governance reference: which trust rules apply to this catalog\n    → verificationMethods: ["sigstore","jws","x509"]',
      },
    },
    {
      id: "5", label: "Cap doc + agent cards land on the same S3 backend", nodeId: "cap-s3", edgeFrom: "ard2", kind: "cap_fetch",
      detail: {
        title: "Step 5 — dns-aid dereferences each entry.url (mcp-server-card.json) from S3",
        rightPaneTabs: ["request"],
        sampleRequest: '// For each catalog entry:\nGET https://ietf-vienna-cap-docs.s3.amazonaws.com/ip-reputation/mcp-server-card.json\n\n// Per ARD §3.4, the catalog entry\'s `url` is the fetchable card;\n// dns-aid follows the URL (or reads inline `data` if used).\n// Endpoint + capabilities + tools come from the DEREFERENCED card,\n// so ARD-sourced agents are as complete as DNS-sourced ones.\n//\n// Response fields dns-aid then tags on the DiscoveredAgent:\n//   capability_source = "agent_card"          (card dereferenced)\n//   endpoint_source   = "http_index_fallback" (catalog-only agent,\n//                        metadata card has no live endpoint; ard_card\n//                        appears only when a card advertises a real one)\n//   trust_manifest    = {identity, attestations[], provenance[], ...}\n//\n// The trust_manifest is the real win — SPIFFE identity + attestations\n// through the ARD path. Same catalog transport, same downstream docs.',
      },
    },
    {
      id: "6", label: "SDK guard (Layer 1)", nodeId: "sdk-guard", edgeFrom: "e9", kind: "jws_verify",
      detail: {
        title: "Step 6 — Same SDK caller-side guard as the DNS-AID path",
        rightPaneTabs: ["request", "response"],
        sampleRequest: 'await check_target_policy(\n    policy_uri="…/policy.json",  # came from ARD entry metadata.policy_uri\n    tool_name="lookup_ip",\n    method="tools/call",\n)',
        sampleResponse: 'PolicyResult(allowed=True)\n[sdk-guard] tool=\'lookup_ip\' → ALLOWED by SDK caller guard\n\n# Layer 1 enforcement runs identically regardless of discovery\n# transport — it only cares about policy_uri.',
      },
    },
    {
      id: "7", label: "Invoke via gateway", nodeId: "gateway", edgeFrom: "e7", kind: "mcp_call",
      detail: {
        title: "Step 7 — Invoke through agentgateway (same backend)",
        rightPaneTabs: ["request"],
        sampleRequest: 'POST http://agentgateway:3000/ip-reputation/mcp\n{"method":"tools/call","params":{"name":"lookup_ip","arguments":{"ip":"185.220.101.45"}}}',
      },
    },
    {
      id: "8", label: "Verdict", nodeId: "fastmcp", edgeFrom: "e8", kind: "mcp_response",
      detail: {
        title: "Step 8 — Same federation backend returns the verdict",
        rightPaneTabs: ["response"],
        sampleResponse: '{"verdict": "malicious", "confidence": 0.95, "sources": ["tor-exit-list", "abuse.ch"]}',
      },
    },
    {
      id: "9", label: "Synthesis", nodeId: "agent", kind: "synthesis",
      detail: {
        title: "Step 9 — Audit chain surfaces the new dns-aid 0.26 ARD fields",
        rightPaneTabs: ["response"],
        sampleResponse: 'agent> **Verdict:** malicious\n       **Confidence:** 0.95\n       **Trust chain (audit):**\n       - Discovery via:      dns-aid MCP (discover_agents_via_dns, use_http_index=True)\n       - Catalog pointer:    _catalog._agents.<slug>.lab.ccdesanity.com → S3  (per-student, DNSSEC-signed)\n       - Pointer trust:      trust_dnssec_pointers=True (off-domain S3 target authorised via DNSSEC)\n       - ARD entry:          urn:air:lab.ccdesanity.com:agent:ip-reputation  (shared global catalog)\n       - capability_source:  agent_card           ← NEW in dns-aid 0.26 (card dereferenced)\n       - endpoint_source:    http_index_fallback  ← NEW in dns-aid 0.26 (catalog-only agent)\n       - trust_manifest.identity:      spiffe://lab.ccdesanity.com/agents/ip-reputation\n       - trust_manifest.attestations:  publisher-identity, SOC2-Type2, ISO27001-2022, GDPR-DPA\n       - Cap doc:            …/ip-reputation/v1.json      (same URL as DNS-AID)\n       - Policy:             …/ip-reputation/policy.json  (same)\n       - SDK guard:          ALLOWED (Layer 1)\n       - Invoked via:        http://agentgateway:3000/ip-reputation/mcp  (same)\n\n// Same MCP tool call, two flags set. Zero agent code changes.\n// dns-aid handled: pointer resolution → catalog fetch → card\n// dereference → trust-manifest surfacing. The agent just consumed\n// the enriched response.',
      },
    },
  ],
};

export const ALL_FLOWS: Flow[] = [IETF_FLOW, IETF_DENIED_FLOW, IETF_ARD_FLOW, IETF_LAYERS_OVERVIEW];
