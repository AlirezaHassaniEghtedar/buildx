"use client";

export function QuestionCard({
  questions,
  onAnswer,
}: {
  questions: string[];
  onAnswer?: (q: string) => void;
}) {
  if (questions.length === 0) return null;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[#FFB84D]/40 bg-[#FFB84D]/10 p-5">
      <h3 className="text-sm font-bold text-[#FFB84D]">
        ❓ چند سؤال برای دقیق‌تر شدن بات
      </h3>
      <ul className="mt-3 flex flex-col gap-2">
        {questions.map((q, i) => (
          <li key={i} className="flex items-start justify-between gap-3 text-sm">
            <span>{q}</span>
            {onAnswer && (
              <button
                onClick={() => onAnswer(q)}
                className="shrink-0 text-xs text-[var(--brand)] hover:underline"
              >
                پاسخ
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
