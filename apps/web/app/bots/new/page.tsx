"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { api } from "@/lib/api";

export default function NewBotPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const bot = await api<{ id: string }>("/api/bots", {
        method: "POST",
        body: JSON.stringify({ name, channel: "sandbox" }),
      });
      router.push(`/bots/${bot.id}/build`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6">
      <h1 className="text-2xl font-bold">بات جدید</h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        اسمش هر چیزی می‌تواند باشد؛ بعداً ایجنت همه‌چیز را ازت می‌پرسد.
      </p>
      <form onSubmit={create} className="mt-8">
        <Label htmlFor="botname">اسم بات</Label>
        <Input
          id="botname"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="مثلاً: رزرو کافه لم"
          required
          minLength={1}
        />
        <Button type="submit" className="mt-6 w-full" disabled={busy}>
          {busy ? "…" : "بریم بسازیم"}
        </Button>
      </form>
    </main>
  );
}
