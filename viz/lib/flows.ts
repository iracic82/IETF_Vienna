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
    sampleRequest?: string;       // syntax-highlighted in right pane
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
// IETF flow: ip-reputation discovery + invocation (9 steps)
// ──────────────────────────────────────────────────────────────────────

const IETF_NODES: Node[] = [
  { id: "strands",    position: { x:   0, y:   0 }, data: { label: "Strands\nclaude-sonnet-4-6" }, type: "explorer" },
  { id: "dns-aid",    position: { x: 240, y:   0 }, data: { label: "dns-aid MCP" }, type: "explorer" },
  { id: "coredns",    position: { x: 480, y:   0 }, data: { label: "CoreDNS\nrecursive + RPZ" }, type: "explorer" },
  { id: "route53",    position: { x: 720, y:   0 }, data: { label: "Route 53\nauth + DNSSEC" }, type: "explorer" },
  { id: "cap-store",  position: { x: 480, y: 160 }, data: { label: "Cap doc store\n(gateway)" }, type: "explorer" },
  { id: "jwks",       position: { x: 720, y: 160 }, data: { label: ".well-known\n/jwks.json" }, type: "explorer" },
  { id: "gateway",    position: { x: 240, y: 320 }, data: { label: "agentgateway\npath route" }, type: "explorer" },
  { id: "fastmcp",    position: { x: 480, y: 320 }, data: { label: "FastMCP\nip-reputation" }, type: "explorer" },
];

const IETF_EDGES: Edge[] = [
  { id: "e1", source: "strands",   target: "dns-aid",    animated: true },
  { id: "e2", source: "dns-aid",   target: "coredns",    animated: true },
  { id: "e3", source: "coredns",   target: "route53",    animated: true },
  { id: "e4", source: "dns-aid",   target: "cap-store",  animated: true },
  { id: "e5", source: "cap-store", target: "jwks",       animated: true },
  { id: "e6", source: "strands",   target: "gateway",    animated: true },
  { id: "e7", source: "gateway",   target: "fastmcp",    animated: true },
];

export const IETF_FLOW: Flow = {
  id: "ietf-discover-ip-reputation",
  title: "Discover & invoke ip-reputation",
  category: "discovery",
  nodes: IETF_NODES,
  edges: IETF_EDGES,
  steps: [
    {
      id: "1", label: "User asks", nodeId: "strands", kind: "tool_call",
      detail: {
        title: "Step 1 — Analyst asks the assistant",
        rightPaneTabs: ["request"],
        sampleRequest: 'analyst> Is 185.220.101.45 malicious?',
      },
    },
    {
      id: "2", label: "Tool selection", nodeId: "strands", edgeFrom: "e1", kind: "tool_call",
      detail: {
        title: "Step 2 — Strands selects discover_agents_via_dns",
        rightPaneTabs: ["request"],
        sampleRequest: 'tools/call {\n  "name": "discover_agents_via_dns",\n  "arguments": {\n    "domain": "${SLUG}.workshop.highvelocitynetworking.com",\n    "protocol": "mcp",\n    "name": "ip-reputation"\n  }\n}',
      },
    },
    {
      id: "3", label: "DNSSEC query", nodeId: "coredns", edgeFrom: "e2", kind: "dns_query",
      detail: {
        title: "Step 3 — dig +dnssec SVCB",
        rightPaneTabs: ["request", "response", "trust"],
        sampleRequest: 'dig +dnssec SVCB _ip-reputation._mcp._agents.${SLUG}.workshop.highvelocitynetworking.com',
        sampleResponse: ';; flags: qr rd ra AD ◄── DNSSEC validated\n_ip-reputation._mcp._agents.${SLUG}... SVCB\n  1 gw.${SLUG}.workshop.hvn.com.\n  alpn="mcp,h2" port=3000\n  key65400="https://gw.${SLUG}.../ip-reputation/cap.json"\n  key65401="<cap-sha256>"\n  key65404="workshop"',
        sampleTrust: '. → workshop.hvn.com → ${SLUG}.workshop.hvn.com\n✓ DS    ✓ DNSKEY    ✓ RRSIG    ✓ AD',
      },
    },
    {
      id: "4", label: "Cap doc fetch", nodeId: "cap-store", edgeFrom: "e4", kind: "cap_fetch",
      detail: {
        title: "Step 4 — GET cap doc through gateway",
        rightPaneTabs: ["request", "response"],
        sampleRequest: 'GET https://gw.${SLUG}.workshop.hvn.com/ip-reputation/cap.json',
        sampleResponse: '{\n  "agent": "ip-reputation",\n  "version": "1.0.0",\n  "tools": ["lookup_ip"],\n  "auth": {"type": "none"},\n  "policy_uri": "https://policies.workshop.hvn.com/ip-rep"\n}\n\nsha256: a7c2f9d1...  (matches SVCB key65401 ✓)',
      },
    },
    {
      id: "5", label: "JWS verify", nodeId: "jwks", edgeFrom: "e5", kind: "jws_verify",
      detail: {
        title: "Step 5 — Verify JWS signature on cap doc",
        rightPaneTabs: ["signature", "trust"],
        sampleSignature: 'JWS header:\n  alg: RS256\n  kid: k-ops-team-2026\n  typ: dns-aid-cap+jws\n\nSignature verified ✓ with k-ops-team-2026 (from JWKS)',
        sampleTrust: 'Signer: k-ops-team-2026 (federation ops team)\nStatus: ACTIVE, not revoked\nTrust:  ✓ in published JWKS',
      },
    },
    {
      id: "6", label: "MCP open", nodeId: "gateway", edgeFrom: "e6", kind: "mcp_open",
      detail: {
        title: "Step 6 — Open MCP connection through agentgateway",
        rightPaneTabs: ["request"],
        sampleRequest: 'POST https://gw.${SLUG}.workshop.hvn.com/ip-reputation/mcp\nContent-Type: application/json\n\n{\n  "jsonrpc": "2.0",\n  "id": 1,\n  "method": "initialize",\n  "params": {"protocolVersion": "2025-03-26"}\n}',
      },
    },
    {
      id: "7", label: "tools/call", nodeId: "fastmcp", edgeFrom: "e7", kind: "mcp_call",
      detail: {
        title: "Step 7 — Invoke lookup_ip",
        rightPaneTabs: ["request"],
        sampleRequest: '{\n  "jsonrpc": "2.0",\n  "id": 2,\n  "method": "tools/call",\n  "params": {\n    "name": "lookup_ip",\n    "arguments": {"ip": "185.220.101.45"}\n  }\n}',
      },
    },
    {
      id: "8", label: "Verdict", nodeId: "fastmcp", kind: "mcp_response",
      detail: {
        title: "Step 8 — Federation returns verdict",
        rightPaneTabs: ["response"],
        sampleResponse: '{\n  "ip": "185.220.101.45",\n  "verdict": "malicious",\n  "confidence": 0.95,\n  "sources": ["tor-exit-list", "abuse.ch"],\n  "tags": ["tor"]\n}',
      },
    },
    {
      id: "9", label: "Synthesis", nodeId: "strands", kind: "synthesis",
      detail: {
        title: "Step 9 — Strands synthesizes answer + audit trail",
        rightPaneTabs: ["response"],
        sampleResponse: 'agent> 185.220.101.45: MALICIOUS (confidence 0.95)\n        sources: tor-exit-list, abuse.ch\n        tags: tor\n\n        audit:\n          discovered via SVCB at _ip-reputation._mcp._agents.${SLUG}...\n          DNSSEC: AD flag verified\n          cap-doc: JWS signed by k-ops-team-2026\n          invoked via gw.${SLUG}.workshop.hvn.com\n          routed by agentgateway',
      },
    },
  ],
};

// ──────────────────────────────────────────────────────────────────────
// IETF2 flows: 4 challenges as separate sidebar entries
// (Stubs for v1 — populated as the challenges are exercised.)
// ──────────────────────────────────────────────────────────────────────

export const IETF2_FLOWS: Flow[] = [
  {
    id: "ietf2-c1-spot-rogue",
    title: "Challenge 1 — Spot the rogue",
    category: "discovery",
    nodes: IETF_NODES,
    edges: IETF_EDGES,
    steps: IETF_FLOW.steps,
  },
  {
    id: "ietf2-c2-contain",
    title: "Challenge 2 — RPZ contain",
    category: "trust",
    nodes: IETF_NODES,
    edges: IETF_EDGES,
    steps: IETF_FLOW.steps,
  },
  {
    id: "ietf2-c3-blast",
    title: "Challenge 3 — Blast radius",
    category: "governance",
    nodes: IETF_NODES,
    edges: IETF_EDGES,
    steps: IETF_FLOW.steps,
  },
  {
    id: "ietf2-c4-harden",
    title: "Challenge 4 — Harden",
    category: "governance",
    nodes: IETF_NODES,
    edges: IETF_EDGES,
    steps: IETF_FLOW.steps,
  },
];

export const ALL_FLOWS: Flow[] = [IETF_FLOW, ...IETF2_FLOWS];
