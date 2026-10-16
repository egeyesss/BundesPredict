import type { FixtureCard } from "./types";

export type FixtureScope = "next_matchday" | "week";

export type FixturesOutcome = { status: "ok"; fixtures: FixtureCard[] } | { status: "error" };

/** How long Next may reuse a fixtures answer. The model refits weekly, so a minute is plenty. */
export const FIXTURES_REVALIDATE_SECONDS = 60;

/**
 * Fetches the public fixtures list from Django on the server. Never throws: a page shows its
 * error state from the returned status instead of crashing the whole route.
 */
export async function loadFixtures(scope: FixtureScope): Promise<FixturesOutcome> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/fixtures?scope=${scope}`, {
      headers: { "x-proxy-secret": process.env.PROXY_SECRET ?? "" },
      next: { revalidate: FIXTURES_REVALIDATE_SECONDS },
    });
    if (!response.ok) return { status: "error" };
    return { status: "ok", fixtures: (await response.json()) as FixtureCard[] };
  } catch {
    return { status: "error" };
  }
}
