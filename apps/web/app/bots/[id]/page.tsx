"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { api } from "@/lib/api";

type Bot = { id: string; name: string; status: string };

export default function BotDashboard() {
  const params = useParams<{ id: string }>();
  const [bot, setBot] = useState<Bot | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!params?.id) return;
    api<Bot>(`/api/bots/${params.id}`)
      .then(setBot)
      .catch(() => setNotFound(true));
  }, [params?.id]);

  if (notFound) return <main className="p-10 text-center">بات پیدا نشد.</main>;

  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="flex items-center justify-between py-6">
        <Logo />
        <ThemeToggle />
      </header>
      <h1 className="text-2xl font-bold">{bot?.name ?? "…"}</h1>
      <p className="mt-4 text-[var(--text-muted)]">
        داشبورد کامل در فاز ۴ ساخته می‌شود؛ فعلاً به استودیوی ساخت سر بزن.
      </p>
      <Link href={`/bots/${params.id}/build`} className="mt-6 inline-block">
        <Button>استودیوی ساخت</Button>
      </Link>
    </main>
  );
}
