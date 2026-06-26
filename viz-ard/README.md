# DNS-AID Explorer

Polished web visualizer for the DNS-AID + agentgateway labs. Modeled
after Auth0's Auth Explorer — animated flow graph on the left,
step-by-step request/response details on the right, scrubber timeline at
the bottom.

## Stack

- **Next.js 16** App Router, standalone output
- **shadcn/ui** style primitives (Tabs, ScrollArea, Badge)
- **Tailwind CSS 4** with custom design tokens (`#0A0E1A` base, `#00E676` accent)
- **React Flow 12** (`@xyflow/react`) for the animated node graph
- **Geist Sans + Geist Mono**
- **Shiki** for code syntax highlighting (in cap-doc previews)
- **Server-Sent Events** consuming the `event-hub` sidecar

## Local dev

```bash
cd viz
npm install
npm run dev
# open http://localhost:3000
```

For dev without a real sandbox, the visualizer still works — it just
shows static flow definitions without live event data. Wire it up to a
running event-hub by setting:

```bash
NEXT_PUBLIC_EVENT_HUB=http://localhost:8888 npm run dev
```

## In the sandbox

`Dockerfile` produces a standalone Next.js build that runs on port 8080.
Docker Compose in each lab adds:

```yaml
services:
  viz:
    build: ../../viz
    container_name: viz
    ports: ["8080:8080"]
    environment:
      NEXT_PUBLIC_EVENT_HUB: http://event-hub:8888
      NEXT_PUBLIC_SANDBOX_SLUG: ${SANDBOX_SLUG}
    depends_on: [event-hub]
```

## Modes

- **Live** — connect to `event-hub` SSE; auto-advance steps as events fire
- **Replay** — disconnect SSE; use the stepper to scrub through the
  current flow at your own pace

## Flow library

Defined in `lib/flows.ts`. Each flow has:

- a list of nodes and edges (React Flow graph)
- a list of steps (each highlights a node + populates the right panel)

To add a new flow, append to `ALL_FLOWS`. The sidebar groups by
`category` ("discovery" | "trust" | "governance").

## Per-lab usage

- **IETF lab** — auto-opens this app in the Instruqt second tab. Speaker
  references it during the 12-minute stage demo.
- **IETF2 lab** — available via the Instruqt tabs; students open as a
  debrief tool. Replay mode is the more common usage here.
