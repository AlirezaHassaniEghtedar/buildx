"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";

type Mode = "login" | "signup";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signup") {
        await api("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, name }),
        });
      } else {
        await api("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }
      router.push("/bots");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.messageFa : "ارتباط با سرور برقرار نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm">
      <h1 className="text-2xl font-bold">{mode === "signup" ? "ساخت حساب" : "ورود"}</h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        {mode === "signup" ? "۵ دقیقه بعد، باتت آمادهٔ تست است." : "خوش برگشتی 👋"}
      </p>

      <div className="mt-8 space-y-5">
        {mode === "signup" && (
          <div>
            <Label htmlFor="name">نام</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </div>
        )}
        <div>
          <Label htmlFor="email">ایمیل</Label>
          <Input id="email" type="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <Label htmlFor="password">رمز عبور</Label>
          <Input
            id="password"
            type="password"
            dir="ltr"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          {mode === "signup" && (
            <p className="mt-1 text-xs text-[var(--text-muted)]">حداقل ۸ کاراکتر</p>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] p-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      )}

      <Button type="submit" className="mt-6 w-full" disabled={busy}>
        {busy ? "لطفاً صبر کن…" : mode === "signup" ? "ساخت حساب" : "ورود"}
      </Button>

      <p className="mt-4 text-center text-sm text-[var(--text-muted)]">
        {mode === "signup" ? (
          <>
            حساب داری؟{" "}
            <Link href="/login" className="text-[var(--brand)] hover:underline">
              وارد شو
            </Link>
          </>
        ) : (
          <>
            حساب نداری؟{" "}
            <Link href="/signup" className="text-[var(--brand)] hover:underline">
              بساز
            </Link>
          </>
        )}
      </p>
    </form>
  );
}
