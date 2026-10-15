import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export const CSRF_COOKIE = "csrftoken";
export const CSRF_HEADER = "X-CSRFToken";

export interface ApiClientOptions {
  /** Empty for the browser (same origin). Server code passes the Django origin. */
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  /** Extra headers on every request, such as `x-proxy-secret` and `cookie` on the server. */
  headers?: HeadersInit;
}

/** The value of one cookie from a `document.cookie` style string, or null. */
export function readCookie(cookies: string, name: string): string | null {
  for (const part of cookies.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

/** Django rejects session-authenticated writes without the CSRF token echoed in a header. */
export function csrfMiddleware(
  getCookies: () => string = () => (typeof document === "undefined" ? "" : document.cookie),
): Middleware {
  return {
    onRequest({ request }) {
      if (SAFE_METHODS.has(request.method.toUpperCase())) return undefined;
      const token = readCookie(getCookies(), CSRF_COOKIE);
      if (token !== null) request.headers.set(CSRF_HEADER, token);
      return request;
    },
  };
}

// Looked up per call: openapi-fetch otherwise keeps the `fetch` it saw at creation, which would
// bypass an MSW interceptor that is installed afterwards.
const lateBoundFetch: typeof globalThis.fetch = (input, init) => globalThis.fetch(input, init);

export function createApiClient({
  baseUrl = "",
  fetch = lateBoundFetch,
  headers,
}: ApiClientOptions = {}) {
  const client = createClient<paths>({
    baseUrl,
    fetch,
    headers,
    credentials: "same-origin",
  });
  client.use(csrfMiddleware());
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;
