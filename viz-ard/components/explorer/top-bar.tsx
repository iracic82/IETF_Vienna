"use client";

import { Compass, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function TopBar({
  connected,
  mode,
  onModeChange,
  sandbox,
}: {
  connected: boolean;
  mode: "live" | "replay";
  onModeChange: (m: "live" | "replay") => void;
  sandbox: string;
}) {
  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)]">
      <div className="flex items-center gap-3">
        <Compass size={18} className="text-[var(--color-accent)]" />
        <span className="font-sans text-[15px] font-semibold tracking-tight">
          DNS-AID Explorer
        </span>
        <Badge variant="default">v1</Badge>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 rounded-md border border-[var(--color-border-subtle)] p-0.5">
          <button
            onClick={() => onModeChange("live")}
            className={`px-2.5 py-1 text-[11px] uppercase tracking-wider rounded-sm transition-colors ${
              mode === "live"
                ? "bg-[var(--color-accent)]/15 text-[var(--color-accent-soft)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            Live
          </button>
          <button
            onClick={() => onModeChange("replay")}
            className={`px-2.5 py-1 text-[11px] uppercase tracking-wider rounded-sm transition-colors ${
              mode === "replay"
                ? "bg-[var(--color-accent)]/15 text-[var(--color-accent-soft)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            Replay
          </button>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
          <Radio
            size={12}
            className={connected ? "text-[var(--color-ok)]" : "text-[var(--color-text-dim)]"}
          />
          {connected ? "connected" : "disconnected"}
        </div>

        <div className="font-mono text-[11px] text-[var(--color-text-dim)]">
          sandbox: <span className="text-[var(--color-text)]">{sandbox}</span>
        </div>
      </div>
    </header>
  );
}
