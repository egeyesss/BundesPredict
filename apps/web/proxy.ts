import { NextResponse, type NextRequest } from "next/server";

import { buildUpstreamHeaders, upstreamUrl } from "@/lib/api/proxy";

/** Sends the backend's paths to Django so the browser only ever talks to this origin. */
export function proxy(request: NextRequest) {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = buildUpstreamHeaders(request.headers, process.env.PROXY_SECRET ?? "");
  return NextResponse.rewrite(upstreamUrl(request.nextUrl, apiBaseUrl), { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/_allauth/:path*", "/accounts/:path*"],
};
