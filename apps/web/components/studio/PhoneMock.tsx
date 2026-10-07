"use client";

import { useEffect, useRef, useState } from "react";

type TranscriptMessage = { direction: "in" | "out"; text: string };

/**
 * PhoneMock — پیش‌نمایش زندهٔ بات داخل قاب موبایل.
 * اتصال به SSE سشن بیلدر؛ رویدادهای تست را به‌صورت چت نشان می‌دهد.
 * در V1 ترنسکریپت تست‌های Sandbox را زنده نمایش می‌دهد.
 */
export function PhoneMock({ sessionId, botId }: { sessionId: string | null; botId: string }) {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionId) return;
    const es = new EventSource(`/api/bots/${botId}/sessions/${sessionId}/events`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as Record<string, unknown>;
        if (data.type === "step" && data.kind === "tests_done") {
          const results = (data.results ?? []) as {
            transcript?: { messages?: TranscriptMessage[] };
          }[];
          const msgs = results.flatMap((r) => r.transcript?.messages ?? []);
          setMessages(msgs);
        }
        if (data.type === "done") es.close();
      } catch {
        /* ignore parse errors */
      }
    };
    return () => es.close();
  }, [sessionId, botId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  return (
    <div className="mx-auto w-[280px] rounded-[2rem] border-4 border-[var(--border)] bg-[var(--bg)] shadow-lg">
      <div className="flex items-center justify-between rounded-t-[1.6rem] bg-[var(--brand)] px-4 py-3 text-white">
        <span className="text-sm font-bold">بات شما</span>
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-[var(--accent)]" : "bg-white/40"}`}
          title={connected ? "متصل" : "قطع"}
        />
      </div>
      <div ref={scrollRef} className="flex h-[360px] flex-col gap-2 overflow-y-auto p-3">
        {messages.length === 0 && (
          <p className="mt-16 text-center text-xs text-[var(--text-muted)]">
            ترنسکریپت تست‌ها اینجا زنده نمایش داده می‌شود.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-6 ${
              m.direction === "in"
                ? "self-end bg-[var(--brand)] text-white"
                : "self-start bg-[var(--surface-2)] text-[var(--text)]"
            }`}
          >
            {m.text}
          </div>
        ))}
      </div>
    </div>
  );
}
