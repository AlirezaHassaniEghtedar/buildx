export class ApiError extends Error {
  code: string;
  messageFa: string;
  details: Record<string, unknown>;

  constructor(code: string, messageFa: string, details: Record<string, unknown> = {}) {
    super(messageFa);
    this.code = code;
    this.messageFa = messageFa;
    this.details = details;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new ApiError(
      (data.code as string) ?? "unknown",
      (data.message_fa as string) ?? "خطای ناشناخته‌ای رخ داد.",
      (data.details as Record<string, unknown>) ?? {},
    );
  }
  return data as T;
}
