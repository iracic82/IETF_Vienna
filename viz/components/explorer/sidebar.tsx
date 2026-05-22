"use client";

import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Flow } from "@/lib/flows";

type Category = "discovery" | "trust" | "governance";

const CATEGORY_LABELS: Record<Category, string> = {
  discovery: "Discovery flows",
  trust: "Trust operations",
  governance: "Governance",
};

export function Sidebar({
  flows,
  activeFlowId,
  onSelect,
}: {
  flows: Flow[];
  activeFlowId: string;
  onSelect: (id: string) => void;
}) {
  const grouped: Record<Category, Flow[]> = {
    discovery: [],
    trust: [],
    governance: [],
  };
  for (const f of flows) grouped[f.category].push(f);

  return (
    <aside className="w-[280px] border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)]">
      <ScrollArea className="h-full">
        <nav className="px-2 py-3 flex flex-col gap-4">
          {(Object.keys(grouped) as Category[]).map((cat) => (
            <section key={cat}>
              <h3 className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-dim)]">
                {CATEGORY_LABELS[cat]}
              </h3>
              <ul className="flex flex-col">
                {grouped[cat].map((f) => {
                  const active = f.id === activeFlowId;
                  return (
                    <li key={f.id}>
                      <button
                        onClick={() => onSelect(f.id)}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded-sm text-[13px] flex items-center gap-2 transition-colors",
                          active
                            ? "bg-[var(--color-bg-elevated)] text-[var(--color-text)] border-l-2 border-[var(--color-accent)]"
                            : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text)]",
                        )}
                      >
                        {active && (
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
                        )}
                        <span className="font-sans">{f.title}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </nav>
      </ScrollArea>
    </aside>
  );
}
