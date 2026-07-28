// Server-side proxy to the prediction API's SSE endpoint.
//
// The browser used to POST to the API directly, which meant its URL shipped in
// the client bundle (NEXT_PUBLIC_*) and anyone could drive the agent loop on
// our Anthropic credit. Now the browser talks to this same-origin route and
// only the server knows where the API lives.
//
// Two headers make the API's protection work:
//   x-proxy-secret — proves the request came from here, so publishing the
//                    API's URL isn't enough to call it.
//   x-client-ip    — the real caller. Every request reaches the API from
//                    Vercel, so without this the API's per-caller rate limit
//                    would put all users in one bucket.
//
// POST route handlers aren't cached by Next, so there's no revalidation config
// to set here.

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
const PROXY_SECRET = process.env.PROXY_SECRET ?? "";

/** Best-effort caller address. Vercel sets x-forwarded-for at the edge. */
function clientIp(request: Request): string {
  // Left-most entry is the original client; the rest are proxy hops.
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  return request.headers.get("x-real-ip")?.trim() ?? "unknown";
}

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/predict/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-proxy-secret": PROXY_SECRET,
        "x-client-ip": clientIp(request),
      },
      body,
      // Node's fetch buffers the whole body without this, which would defeat
      // the point of streaming the agent's progress back.
      // @ts-expect-error -- undici-only option, not in the DOM fetch types.
      duplex: "half",
    });
  } catch {
    return Response.json(
      { detail: "Could not reach the prediction service." },
      { status: 502 },
    );
  }

  // Pass non-2xx through unchanged so the client keeps its existing handling
  // for 429 (rate limited), 422 (query too long), and 503 (model not ready).
  if (!upstream.ok || upstream.body === null) {
    const detail = await upstream.text().catch(() => "");
    return new Response(detail, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      // Stops buffering proxies from holding frames back until the end.
      "X-Accel-Buffering": "no",
    },
  });
}
