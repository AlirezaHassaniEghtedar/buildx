"use client";

const STEPS: { key: string; label: string }[] = [
  { key: "intake", label: "دریافت درخواست" },
  { key: "generate_spec", label: "ساخت پیش‌نویس" },
  { key: "validate", label: "اعتبارسنجی" },
  { key: "design_tests", label: "طراحی تست‌ها" },
  { key: "run_sandbox", label: "اجرای Sandbox" },
  { key: "confirm", label: "تأیید نهایی" },
];

export type StepStatus = "pending" | "active" | "done" | "failed";

export function StepTimeline({
  statuses,
}: {
  statuses: Record<string, StepStatus>;
}) {
  return (
    <ol className="flex flex-col gap-1" aria-label="مراحل ساخت بات">
      {STEPS.map((s, i) => {
        const st = statuses[s.key] ?? "pending";
        return (
          <li key={s.key} className="flex items-center gap-3">
            <span
              className={[
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-colors",
                st === "done" && "border-transparent bg-[var(--brand)] text-white",
                st === "active" && "border-[var(--brand)] text-[var(--brand)]",
                st === "failed" && "border-transparent bg-[var(--danger)] text-white",
                st === "pending" && "border-[var(--border)] text-[var(--text-muted)]",
              ].join(" ")}
            >
              {st === "done" ? "✓" : st === "failed" ? "✕" : i + 1}
            </span>
            <span
              className={[
                "text-sm",
                st === "pending" ? "text-[var(--text-muted)]" : "text-[var(--text)]",
                st === "active" && "font-semibold",
              ].join(" ")}
            >
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
