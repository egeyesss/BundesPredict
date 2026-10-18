import { CSRF_COOKIE, CSRF_HEADER, readCookie } from "@/lib/api/client";

export const ALLAUTH_BASE = "/_allauth/browser/v1";

export type AuthFailure = "invalid_email" | "invalid_code" | "expired" | "rate_limited" | "network" | "unexpected";
export type AuthResult = { ok: true } | { ok: false; reason: AuthFailure };

const OK: AuthResult = { ok: true };
const fail = (reason: AuthFailure): AuthResult => ({ ok: false, reason });

type Flow = { id: string; is_pending?: boolean };
type AllauthBody = { data?: { flows?: Flow[] }; errors?: { code?: string; param?: string }[] };

async function call(path: string, method: "GET" | "POST" | "DELETE", body?: unknown): Promise<{ response: Response; json: AllauthBody } | null> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    const token = readCookie(document.cookie, CSRF_COOKIE) ?? (await ensureCsrfCookie());
    if (token) headers[CSRF_HEADER] = token;
  }
  try {
    const response = await fetch(new URL(`${ALLAUTH_BASE}${path}`, window.location.origin), {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json = (await response.json().catch(() => ({}))) as AllauthBody;
    return { response, json };
  } catch {
    return null;
  }
}

/** Every allauth browser endpoint sets the CSRF cookie, so a read of the session is enough to get one. */
export async function ensureCsrfCookie(): Promise<string | null> {
  await call("/auth/session", "GET");
  return readCookie(document.cookie, CSRF_COOKIE);
}

/** allauth answers "code sent" and "verify this next" with a 401 that names the pending flow. */
async function startFlow(path: string, email: string, flow: string): Promise<AuthResult> {
  const result = await call(path, "POST", { email });
  if (!result) return fail("network");
  const { response, json } = result;
  if (response.status === 429) return fail("rate_limited");
  if (response.status === 400) return fail("invalid_email");
  const pending = json.data?.flows?.some((candidate) => candidate.id === flow && candidate.is_pending);
  return response.status === 401 && pending ? OK : fail("unexpected");
}

async function completeFlow(path: string, body: Record<string, string>): Promise<AuthResult> {
  const result = await call(path, "POST", body);
  if (!result) return fail("network");
  const { response } = result;
  if (response.ok) return OK;
  if (response.status === 400) return fail("invalid_code");
  if (response.status === 401) return fail("expired");
  if (response.status === 429) return fail("rate_limited");
  return fail("unexpected");
}

export const requestLoginCode = (email: string) => startFlow("/auth/code/request", email, "login_by_code");
export const confirmLoginCode = (code: string) => completeFlow("/auth/code/confirm", { code });
export const signUp = (email: string) => startFlow("/auth/signup", email, "verify_email");
export const verifyEmail = (code: string) => completeFlow("/auth/email/verify", { key: code });

/** Logging out answers 401 because the session it describes no longer exists. */
export async function signOut(): Promise<AuthResult> {
  const result = await call("/auth/session", "DELETE");
  if (!result) return fail("network");
  return result.response.status === 401 || result.response.ok ? OK : fail("unexpected");
}
