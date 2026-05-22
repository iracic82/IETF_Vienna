"use client";

import { useEffect, useRef, useState } from "react";

export type ExplorerEvent = {
  source: string;        // "dns-aid" | "mcp:<name>" | "coredns" | "agentgateway"
  kind: string;          // "rpc" | "tools_call" | "dns_query" | "dns_response" | ...
  ts: number;            // epoch seconds
  [key: string]: unknown;
};

const DEFAULT_HUB = process.env.NEXT_PUBLIC_EVENT_HUB ?? "http://localhost:8888";

export function useEventStream(opts: { paused?: boolean } = {}) {
  const [events, setEvents] = useState<ExplorerEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (opts.paused) {
      sourceRef.current?.close();
      sourceRef.current = null;
      setConnected(false);
      return;
    }

    const es = new EventSource(`${DEFAULT_HUB}/stream`);
    sourceRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data) as ExplorerEvent;
        setEvents((prev) => [...prev.slice(-499), evt]);
      } catch {
        // ignore malformed frames
      }
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [opts.paused]);

  return { events, connected };
}

export async function fetchRecentEvents(n = 100): Promise<ExplorerEvent[]> {
  try {
    const r = await fetch(`${DEFAULT_HUB}/events?since=${n}`, { cache: "no-store" });
    if (!r.ok) return [];
    return (await r.json()) as ExplorerEvent[];
  } catch {
    return [];
  }
}
