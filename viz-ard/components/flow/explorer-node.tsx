"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";

type ExplorerNodeData = {
  label: string;
  active?: boolean;
};

export function ExplorerNode({ data }: NodeProps & { data: ExplorerNodeData }) {
  const lines = data.label.split("\n");
  return (
    <div
      className={cn(
        "rounded-md px-4 py-3 min-w-[180px]",
        "bg-[var(--color-bg-panel)]",
        "border transition-all duration-300",
        data.active
          ? "border-[var(--color-accent)] shadow-[0_0_24px_-4px_var(--color-accent)]"
          : "border-[var(--color-border-strong)]",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-[var(--color-flow)] !w-2 !h-2 !border-0" />
      <div className="flex flex-col gap-0.5">
        <div
          className={cn(
            "font-mono text-[13px] font-medium",
            data.active ? "text-[var(--color-accent-soft)]" : "text-[var(--color-text)]",
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
    </div>
  );
}

export const explorerNodeTypes = { explorer: ExplorerNode };
