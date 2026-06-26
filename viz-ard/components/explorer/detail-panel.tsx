"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FlowStep } from "@/lib/flows";

export function DetailPanel({ step }: { step: FlowStep | null }) {
  if (!step) {
    return (
      <aside className="w-[420px] border-l border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)] p-4">
        <p className="text-[12px] text-[var(--color-text-dim)]">No step selected.</p>
      </aside>
    );
  }

  const tabs = step.detail.rightPaneTabs;
  const defaultTab = tabs[0];

  return (
    <aside className="w-[420px] border-l border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)] flex flex-col">
      <div className="px-4 py-3 border-b border-[var(--color-border-subtle)]">
        <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-dim)] font-semibold">
          Step {step.id}
        </div>
        <h2 className="text-[14px] font-semibold mt-0.5">{step.detail.title}</h2>
      </div>

      <Tabs defaultValue={defaultTab} className="flex-1 flex flex-col">
        <TabsList className="px-3">
          {tabs.map((t) => (
            <TabsTrigger key={t} value={t}>
              {t}
            </TabsTrigger>
          ))}
        </TabsList>

        <ScrollArea className="flex-1">
          <div className="p-4">
            {step.detail.sampleRequest && tabs.includes("request") && (
              <TabsContent value="request">
                <CodeBlock>{step.detail.sampleRequest}</CodeBlock>
              </TabsContent>
            )}
            {step.detail.sampleResponse && tabs.includes("response") && (
              <TabsContent value="response">
                <CodeBlock>{step.detail.sampleResponse}</CodeBlock>
              </TabsContent>
            )}
            {step.detail.sampleSignature && tabs.includes("signature") && (
              <TabsContent value="signature">
                <CodeBlock>{step.detail.sampleSignature}</CodeBlock>
              </TabsContent>
            )}
            {step.detail.sampleTrust && tabs.includes("trust") && (
              <TabsContent value="trust">
                <CodeBlock>{step.detail.sampleTrust}</CodeBlock>
              </TabsContent>
            )}
          </div>
        </ScrollArea>
      </Tabs>
    </aside>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre className="font-mono text-[12.5px] leading-[1.55] text-[var(--color-text)] bg-[var(--color-bg-code)] border border-[var(--color-border-subtle)] rounded p-3 whitespace-pre-wrap break-words">
      {children}
    </pre>
  );
}
