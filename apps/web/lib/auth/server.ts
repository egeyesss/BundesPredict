import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { Me } from "@/lib/api/types";

import { loginUrl } from "./next-path";

export type MeOutcome = { status: "ok"; me: Me } | { status: "signed_out" } | { status: "error" };

/**
 * Asks Django who the visitor is, forwarding their cookie. Never throws: a backend hiccup is
 * `error`, which callers must not confuse with `signed_out` or they would bounce signed-in users.
 */
export async function getMe(): Promise<MeOutcome> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/me`, {
      headers: { "x-proxy-secret": process.env.PROXY_SECRET ?? "", cookie: (await cookies()).toString() },
      cache: "no-store",
    });
    if (response.status === 401) return { status: "signed_out" };
    if (!response.ok) return { status: "error" };
    return { status: "ok", me: (await response.json()) as Me };
  } catch {
    return { status: "error" };
  }
}

/** The route guard for pages that need a session: redirects to login, or throws to the error boundary. */
export async function requireMe(nextPath: string): Promise<Me> {
  const outcome = await getMe();
  if (outcome.status === "signed_out") redirect(loginUrl(nextPath));
  if (outcome.status === "error") throw new Error("Could not load your account from the API.");
  return outcome.me;
}
