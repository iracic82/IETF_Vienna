"use client";

import { useEffect, useMemo, useState } from "react";
import { ReactFlow, Background, Controls, MarkerType, type Node, type Edge } from "@xyflow/react";

import { TopBar } from "@/components/explorer/top-bar";
import { Sidebar } from "@/components/explorer/sidebar";
import { DetailPanel } from "@/components/explorer/detail-panel";
import { Stepper } from "@/components/explorer/stepper";
import { explorerNodeTypes } from "@/components/flow/explorer-node";

import { ALL_FLOWS, type Flow } from "@/lib/flows";
import { useEventStream } from "@/lib/events";

export default function Page() {
  const [mode, setMode] = useState<"live" | "replay">("live");
  const [activeFlowId, setActiveFlowId] = useState<string>(ALL_FLOWS[0].id);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  const flow = useMemo<Flow>(
    () => ALL_FLOWS.find((f) => f.id === activeFlowId) ?? ALL_FLOWS[0],
    [activeFlowId],
  );

  const currentStep = flow.steps[step] ?? null;
  const activeNodeId = currentStep?.nodeId;

  const decoratedNodes: Node[] = flow.nodes.map((n) => ({
    ...n,
    data: { ...n.data, active: n.id === activeNodeId },
  }));

  // Edge styling pass:
  //   - Only the ACTIVE edge shows its label (inactive labels stripped
  //     so 10 edges don't fight for the same horizontal band).
  //   - Active edge: full opacity, accent colour, slightly thicker.
  //   - Inactive edges: dim grey so they read as spatial context only.
  //   - Labels get a solid panel-coloured background with a subtle
  //     border so they sit cleanly on top of the dotted grid.
  const decoratedEdges: Edge[] = flow.edges.map((e) => {
    const isActive = e.id === currentStep?.edgeFrom;
    return {
      ...e,
      type: "smoothstep",
      label: isActive ? e.label : undefined,
      className: isActive ? "flow-edge-animated" : undefined,
      style: {
        stroke: isActive ? "var(--color-accent)" : "var(--color-border-strong)",
        strokeWidth: isActive ? 2.2 : 1,
        opacity: isActive ? 1 : 0.35,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 14,
        height: 14,
        color: isActive ? "var(--color-accent)" : "var(--color-border-strong)",
      },
      labelStyle: {
        fontSize: 11,
        fontWeight: 600,
        fill: "var(--color-text)",
      },
      labelBgStyle: {
        fill: "var(--color-bg-panel)",
        fillOpacity: 1,
        stroke: "var(--color-accent)",
        strokeWidth: 1,
      },
      labelBgPadding: [8, 5] as [number, number],
      labelBgBorderRadius: 3,
    };
  });

  const { events, connected } = useEventStream({ paused: mode !== "live" });

  // Live mode: auto-advance step when a relevant event arrives.
  useEffect(() => {
    if (mode !== "live") return;
    if (events.length === 0) return;
    const latest = events[events.length - 1];
    // very simple mapping for v1; tighten as event taxonomy matures
    if (latest.kind === "tools_call" || latest.kind === "rpc") {
      setStep((s) => Math.min(flow.steps.length - 1, s + 1));
    }
  }, [events, flow.steps.length, mode]);

  // Replay/play autoplay timer
  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => {
      setStep((s) => {
        const next = s + 1;
        if (next >= flow.steps.length) {
          setPlaying(false);
          return s;
        }
        return next;
      });
    }, 1400);
    return () => clearTimeout(t);
  }, [step, playing, flow.steps.length]);

  return (
    <div className="h-screen w-screen flex flex-col bg-[var(--color-bg-base)] text-[var(--color-text)]">
      <TopBar
        connected={connected}
        mode={mode}
        onModeChange={setMode}
        sandbox={process.env.NEXT_PUBLIC_SANDBOX_SLUG ?? "local"}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          flows={ALL_FLOWS}
          activeFlowId={activeFlowId}
          onSelect={(id) => {
            setActiveFlowId(id);
            setStep(0);
          }}
        />

        <main className="flex-1 relative">
          <ReactFlow
            key={activeFlowId}
            nodes={decoratedNodes}
            edges={decoratedEdges}
            nodeTypes={explorerNodeTypes}
            fitView
            fitViewOptions={{ padding: 0.25 }}
            proOptions={{ hideAttribution: false }}
          >
            <Background gap={20} size={1} />
            <Controls position="bottom-left" showInteractive={false} />
          </ReactFlow>
        </main>

        <DetailPanel step={currentStep} />
      </div>

      <Stepper
        flow={flow}
        current={step}
        playing={playing}
        onStep={setStep}
        onPlay={setPlaying}
      />
    </div>
  );
}
