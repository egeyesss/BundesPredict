export const DEFAULT_NEXT_PATH = "/matchday";

/** Accepts only a same-site absolute path, so `?next=` can never become an open redirect. */
export function safeNextPath(raw: string | string[] | undefined): string {
  if (typeof raw !== "string") return DEFAULT_NEXT_PATH;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return DEFAULT_NEXT_PATH;
  if (/[\u0000-\u001f]/.test(raw)) return DEFAULT_NEXT_PATH;
  if (raw === "/login" || raw.startsWith("/login?") || raw.startsWith("/login/")) return DEFAULT_NEXT_PATH;
  return raw;
}

export function loginUrl(next: string): string {
  return next === DEFAULT_NEXT_PATH ? "/login" : `/login?next=${encodeURIComponent(next)}`;
}
