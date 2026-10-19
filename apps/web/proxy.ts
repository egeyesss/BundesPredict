import { NextResponse, type NextRequest } from "next/server";

import { buildUpstreamHeaders, upstreamUrl } from "@/lib/api/proxy";
import { loginUrl } from "@/lib/auth/next-path";
import { hasSessionCookie, isGuardedPath } from "@/lib/auth/session-cookie";

/**
 * Sends the backend's paths to Django so the browser only ever talks to this origin, and answers
 * session-only pages with a real 307 when there is no session cookie. Left to `requireMe` alone,
 * a page with a `loading.tsx` has already started streaming, so its redirect arrives as a 200.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isGuardedPath(pathname)) {
    if (hasSessionCookie(request.cookies)) return NextResponse.next();
    return NextResponse.redirect(new URL(loginUrl(`${pathname}${search}`), request.url));
  }

  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = buildUpstreamHeaders(request.headers, process.env.PROXY_SECRET ?? "");
  return NextResponse.rewrite(upstreamUrl(request.nextUrl, apiBaseUrl), { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/_allauth/:path*", "/accounts/:path*", "/account/:path*", "/chat/:path*"],
};
