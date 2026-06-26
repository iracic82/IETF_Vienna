"use client";

import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Flow } from "@/lib/flows";

export function Stepper({
  flow,
  current,
  playing,
  onStep,
  onPlay,
}: {
  flow: Flow;
  current: number;
  playing: boolean;
  onStep: (i: number) => void;
  onPlay: (p: boolean) => void;
}) {
  const totalSteps = flow.steps.length;
  return (
    <footer className="h-14 flex items-center justify-between gap-4 px-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)]">
      <div className="flex items-center gap-1">
        <Btn onClick={() => onStep(0)}><ChevronFirst size={16} /></Btn>
        <Btn onClick={() => onStep(Math.max(0, current - 1))}><ChevronLeft size={16} /></Btn>
        <Btn onClick={() => onPlay(!playing)}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </Btn>
        <Btn onClick={() => onStep(Math.min(totalSteps - 1, current + 1))}><ChevronRight size={16} /></Btn>
        <Btn onClick={() => onStep(totalSteps - 1)}><ChevronLast size={16} /></Btn>
      </div>

      <div className="flex-1 flex items-center gap-2">
        <span className="text-[11px] text-[var(--color-text-muted)] font-mono w-20">
          Step {current + 1} / {totalSteps}
        </span>
        <div className="flex-1 flex items-center gap-1">
          {flow.steps.map((_, i) => {
            const passed = i <= current;
            return (
              <button
                key={i}
                onClick={() => onStep(i)}
                aria-label={`Jump to step ${i + 1}`}
                className={cn(
                  "h-2 flex-1 rounded-full transition-colors",
                  passed ? "bg-[var(--color-accent)]" : "bg-[var(--color-border-strong)]",
                  i === current && "ring-1 ring-[var(--color-accent-soft)] ring-offset-1 ring-offset-[var(--color-bg-panel)]",
                )}
              />
            );
          })}
        </div>
      </div>

      <div className="text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-dim)] font-mono">
        {flow.title}
      </div>
    </footer>
  );
}

function Btn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="h-8 w-8 flex items-center justify-center rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-elevated)] transition-colors"
    >
      {children}
    </button>
  );
}
