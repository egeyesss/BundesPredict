import { cookies } from "next/headers";

import type { AdminMetrics } from "@/lib/api/types";

export const RANGES = [7, 30, 90] as const;
export type Range = (typeof RANGES)[number];

export type MetricsOutcome =
  | { status: "ok"; metrics: AdminMetrics }
  | { status: "signed_out" | "forbidden" | "error" };

export function parseRange(value: string | string[] | undefined): Range {
  return RANGES.find((range) => String(range) === value) ?? 30;
}

/** Fetches the dashboard numbers with the visitor's cookie. Never throws, so the page can pick its state. */
export async function loadAdminMetrics(days: Range): Promise<MetricsOutcome> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/admin/metrics?days=${days}`, {
      headers: { "x-proxy-secret": process.env.PROXY_SECRET ?? "", cookie: (await cookies()).toString() },
      cache: "no-store",
    });
    if (response.status === 401) return { status: "signed_out" };
    if (response.status === 403) return { status: "forbidden" };
    if (!response.ok) return { status: "error" };
    return { status: "ok", metrics: (await response.json()) as AdminMetrics };
  } catch {
    return { status: "error" };
  }
}
