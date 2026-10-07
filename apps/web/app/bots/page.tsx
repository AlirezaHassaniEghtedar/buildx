"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { api } from "@/lib/api";

type Bot = {
  id: string;
  name: string;
  status: "draft" | "published" | "paused";
  channel: string | null;
};

const statusFa: Record<Bot["status"], string> = {
  draft: "پیش‌نویس",
  published: "زنده",
  paused: "متوقف",
};

const statusColor: Record<Bot["status"], string> = {
  draft: "var(--text-muted)",
  published: "var(--success)",
  paused: "var(--warning)",
};

export default function BotsPage() {
  const [bots, setBots] = useState<Bot[] | null>(null);

  useEffect(() => {
    api<Bot[]>("/api/bots")
      .then(setBots)
      .catch(() => setBots([]));
  }, []);

  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="flex items-center justify-between py-6">
        <Logo />
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await api("/api/auth/logout", { method: "POST" });
              location.href = "/login";
            }}
          >
            خروج
          </Button>
        </div>
      </header>

      <div className="flex items-center justify-between py-8">
        <h1 className="text-2xl font-bold">بات‌های من</h1>
        <Link href="/bots/new">
          <Button size="sm">
            <Plus size={16} />
            بات جدید
          </Button>
        </Link>
      </div>

      {bots === null ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-36 animate-pulse rounded-[var(--radius-xl)] bg-[var(--surface-2)]" />
          ))}
        </div>
      ) : bots.length === 0 ? (
        <div className="rounded-[var(--radius-xl)] border border-dashed border-[var(--border)] py-20 text-center">
          <p className="text-lg font-semibold">هنوز باتی نساخته‌ای</p>
          <p className="mt-2 text-[var(--text-muted)]">اولین باتت را در ۵ دقیقه بساز؛ فقط چند سؤال ساده.</p>
          <Link href="/bots/new" className="mt-6 inline-block">
            <Button>ساخت اولین بات</Button>
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {bots.map((b) => (
            <Link
              key={b.id}
              href={`/bots/${b.id}`}
              className="rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface-1)] p-6 shadow-[var(--shadow-1)] transition-shadow duration-[var(--dur)] hover:shadow-[var(--shadow-2)]"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{b.name}</h3>
                <span className="text-xs font-medium" style={{ color: statusColor[b.status] }}>
                  ● {statusFa[b.status]}
                </span>
              </div>
              <p className="mt-3 text-sm text-[var(--text-muted)]">
                {b.channel === "telegram" ? "تلگرام" : b.channel === "bale" ? "بله" : "سن‌باکس"}
              </p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
