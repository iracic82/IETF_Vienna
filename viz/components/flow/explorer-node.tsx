"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";

type ExplorerNodeData = {
  label: string;
  active?: boolean;
  denied?: boolean;
};

export function ExplorerNode({ data }: NodeProps & { data: ExplorerNodeData }) {
  const lines = data.label.split("\n");
  return (
    <div
      className={cn(
        "rounded-md px-4 py-3 min-w-[180px]",
        "bg-[var(--color-bg-panel)]",
        "border transition-all duration-300",
        data.denied
          ? "border-[#f87171] shadow-[0_0_24px_-4px_#f87171]"
          : data.active
            ? "border-[var(--color-accent)] shadow-[0_0_24px_-4px_var(--color-accent)]"
            : "border-[var(--color-border-strong)]",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-[var(--color-flow)] !w-2 !h-2 !border-0" />
      {/* Invisible top-target anchor: lets specific edges (e.g. the MCP
          call agent→gateway) enter from above instead of the left, so
          they don't route through nodes sharing the source's row. */}
      <Handle type="target" position={Position.Top} id="t" className="!opacity-0 !w-2 !h-2 !border-0" />
      <div className="flex flex-col gap-0.5">
        <div
          className={cn(
            "font-mono text-[13px] font-medium",
            data.denied
              ? "text-[#fca5a5]"
              : data.active
                ? "text-[var(--color-accent-soft)]"
                : "text-[var(--color-text)]",
          )}
        >
          {lines[0]}
        </div>
        {lines[1] && (
          <div className="font-mono text-[10.5px] text-[var(--color-text-dim)] tracking-wide">
            {lines[1]}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-[var(--color-flow)] !w-2 !h-2 !border-0" />
      {/* Invisible bottom-source anchor (see top-target note above). */}
      <Handle type="source" position={Position.Bottom} id="b" className="!opacity-0 !w-2 !h-2 !border-0" />
    </div>
  );
}

export const explorerNodeTypes = { explorer: ExplorerNode };
