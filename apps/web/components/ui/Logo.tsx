export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
        <rect x="5" y="9" width="22" height="16" rx="5" stroke="var(--brand)" strokeWidth="2" />
        <circle cx="12.5" cy="17" r="2" fill="var(--accent)" />
        <circle cx="19.5" cy="17" r="2" fill="var(--accent)" />
        <path d="M16 9V4" stroke="var(--brand)" strokeWidth="2" strokeLinecap="round" />
        <path d="M16 3.2 17 5.4 19.2 6.4 17 7.4 16 9.6 15 7.4 12.8 6.4 15 5.4Z" fill="var(--warm)" />
      </svg>
      <span className="text-lg font-bold">BotForge</span>
    </span>
  );
}
