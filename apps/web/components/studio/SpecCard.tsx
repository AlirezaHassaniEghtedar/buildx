"use client";

const MODULE_FA: Record<string, { label: string; emoji: string }> = {
  booking: { label: "رزرو و نوبت‌دهی", emoji: "📅" },
  ordering: { label: "سفارش‌گیری", emoji: "🛒" },
  faq: { label: "پاسخ به سؤالات", emoji: "💬" },
  notify: { label: "اطلاع‌رسانی", emoji: "🔔" },
};

type SpecModule = {
  type: string;
  items?: { title: string; capacity?: number; price?: number | null }[];
  categories?: { items: { title: string; price: number }[] }[];
  entries?: { questions: string[] }[];
  collect_fields?: { label: string; type: string }[];
};

export type SpecData = {
  meta?: { name?: string; welcome_message?: string; tone?: string };
  modules?: SpecModule[];
};

const TONE_FA: Record<string, string> = {
  friendly: "خودمونی",
  formal: "رسمی",
  playful: "شوخ",
};

export function SpecCard({ spec }: { spec: SpecData }) {
  if (!spec?.meta) return null;
  const tone = spec.meta.tone ? TONE_FA[spec.meta.tone] ?? spec.meta.tone : "";

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)] p-5">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-base font-bold">پیش‌نویس بات: {spec.meta.name}</h3>
        {tone && (
          <span className="rounded-full bg-[var(--brand)]/10 px-2 py-0.5 text-xs text-[var(--brand)]">
            لحن {tone}
          </span>
        )}
      </div>
      {spec.meta.welcome_message && (
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          پیام خوش‌آمد: «{spec.meta.welcome_message}»
        </p>
      )}
      <ul className="mt-4 flex flex-col gap-3">
        {(spec.modules ?? []).map((m, i) => (
          <li key={i} className="rounded-[var(--radius-md)] border border-[var(--border)] p-3">
            <p className="text-sm font-semibold">
              {MODULE_FA[m.type]?.emoji ?? "⚙️"} {MODULE_FA[m.type]?.label ?? m.type}
            </p>
            {"items" in m && m.items && m.items.length > 0 && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {m.items.map((it) => it.title).join("، ")}
                {m.items[0]?.capacity ? ` — ظرفیت ${m.items[0].capacity} نفر` : ""}
              </p>
            )}
            {"categories" in m && m.categories && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {m.categories.flatMap((c) => c.items.map((it) => it.title)).join("، ")}
              </p>
            )}
            {"entries" in m && m.entries && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {m.entries.map((e) => e.questions[0]).join("، ")}
              </p>
            )}
            {"collect_fields" in m && m.collect_fields && m.collect_fields.length > 0 && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                اطلاعات دریافتی: {m.collect_fields.map((f) => f.label).join("، ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
