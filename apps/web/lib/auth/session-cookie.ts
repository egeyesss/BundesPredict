export const SESSION_COOKIE = "sessionid";
export const MOCK_PLAN_COOKIE = "bp_mock_plan";

const GUARDED_PREFIXES = ["/account", "/chat", "/admin"];

export function isGuardedPath(pathname: string): boolean {
  return GUARDED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * Whether the request carries a session cookie at all. This only says "might be signed in":
 * Django still decides in `requireMe`, so an expired cookie costs one extra redirect, not access.
 */
export function hasSessionCookie(cookies: { has(name: string): boolean }): boolean {
  if (cookies.has(SESSION_COOKIE)) return true;
  return process.env.API_MOCKING === "enabled" && cookies.has(MOCK_PLAN_COOKIE);
}

/**
 * Where a signed-in visitor should land instead of the marketing page. The landing page is
 * static, so the proxy answers this before the page renders rather than the page asking Django.
 */
export function signedInHomePath(pathname: string, cookies: { has(name: string): boolean }): string | null {
  return pathname === "/" && hasSessionCookie(cookies) ? "/matchday" : null;
}
