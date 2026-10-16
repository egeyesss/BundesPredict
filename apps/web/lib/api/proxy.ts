/** Headers the Django backend relies on, built from the browser's request in `proxy.ts`. */
export function buildUpstreamHeaders(incoming: Headers, proxySecret: string): Headers {
  const headers = new Headers(incoming);
  headers.set("x-proxy-secret", proxySecret);
  headers.set("x-client-ip", clientIp(incoming));
  headers.set("x-forwarded-host", incoming.get("host") ?? "");
  headers.set("x-forwarded-proto", incoming.get("x-forwarded-proto") ?? "http");
  return headers;
}

/** Vercel overwrites x-forwarded-for at the edge, so its left-most entry is the real caller. */
function clientIp(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  return headers.get("x-real-ip")?.trim() || "unknown";
}

export function upstreamUrl(requestUrl: URL, apiBaseUrl: string): URL {
  return new URL(`${requestUrl.pathname}${requestUrl.search}`, apiBaseUrl);
}
