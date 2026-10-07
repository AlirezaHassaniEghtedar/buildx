import { ArrowLeft, MessageSquareText, FlaskConical, Rocket } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const steps = [
  {
    icon: MessageSquareText,
    title: "۱. تعریف کن",
    body: "به زبان خودت بگو چه باتی می‌خواهی؛ ایجنت سؤال‌های دقیق را ازت می‌پرسد.",
  },
  {
    icon: FlaskConical,
    title: "۲. تست کن",
    body: "ایجنت خودش سناریوهای آزمایشی را اجرا می‌کند؛ ظرفیت پر، لغو رزرو، شمارهٔ تلفن غلط…",
  },
  {
    icon: Rocket,
    title: "۳. منتشر کن",
    body: "توکن بات را از BotFather بگیر و تمام؛ بات واقعاً روی تلگرام یا بله بالا می‌آید.",
  },
];

export default function Landing() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="flex items-center justify-between py-6">
        <Logo />
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link href="/login">
            <Button variant="ghost" size="sm">
              ورود
            </Button>
          </Link>
          <Link href="/signup">
            <Button size="sm">ثبت‌نام</Button>
          </Link>
        </div>
      </header>

      <section className="py-20 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-[1.4] md:text-[52px] md:leading-[1.35]">
          باتِ کسب‌وکارت را
          <span className="text-[var(--brand)]"> با یک گفت‌وگو </span>
          بساز
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-[var(--text-muted)]">
          رزرو کافه و کارگاه، سفارش منو، لیست انتظار و پاسخ خودکار — بدون یک خط کدنویسی.
          ایجنت BotForge مشخصات را می‌پرسد، می‌سازد، تست می‌کند و منتشر می‌کند.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link href="/signup">
            <Button size="lg">
              شروع کن — رایگان
              <ArrowLeft size={18} />
            </Button>
          </Link>
        </div>
        <div className="mt-4 text-sm text-[var(--text-muted)]">۵ دقیقه تا اولین بات واقعی</div>
      </section>

      <section className="grid gap-6 pb-24 md:grid-cols-3">
        {steps.map((s) => (
          <div
            key={s.title}
            className="rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface-1)] p-8 shadow-[var(--shadow-1)]"
          >
            <s.icon size={28} strokeWidth={1.75} className="text-[var(--accent)]" />
            <h3 className="mt-4 text-lg font-semibold">{s.title}</h3>
            <p className="mt-2 leading-7 text-[var(--text-muted)]">{s.body}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-[var(--border)] py-8 text-center text-sm text-[var(--text-muted)]">
        BotForge — ساخته‌شده برای کسب‌وکارهای کوچک ایرانی
      </footer>
    </main>
  );
}
