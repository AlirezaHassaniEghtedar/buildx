import clsx from "clsx";
import type { InputHTMLAttributes, LabelHTMLAttributes } from "react";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(
        "h-11 w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-1)] px-4 text-[15px] text-[var(--text)] outline-none transition-colors duration-[var(--dur)] placeholder:text-[var(--text-muted)] focus:border-[var(--brand)]",
        className,
      )}
      {...rest}
    />
  );
}

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={clsx("mb-2 block text-sm font-medium text-[var(--text)]", className)} {...rest} />
  );
}
