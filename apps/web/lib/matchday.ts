import type { FixtureCard } from "@/lib/api/types";

export type KickoffFormat = { timeZone?: string; locale?: string };

/** "Fri 2:30 PM" in the viewer's timezone, or the one given. */
export function formatKickoff(kickoffUtc: string, { timeZone, locale }: KickoffFormat = {}): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(kickoffUtc));
}

/** The API sends the stored season, "2627"; the league writes 2026/27. */
export function seasonLabel(season: string): string {
  const compact = /^(\d{2})(\d{2})$/.exec(season);
  if (!compact) return season.replace("-", "/");
  const century = Number(compact[1]) >= 50 ? "19" : "20";
  return `${century}${compact[1]}/${compact[2]}`;
}

export type MatchdayGroup = { matchday: number; fixtures: FixtureCard[] };

export function groupByMatchday(fixtures: readonly FixtureCard[]): MatchdayGroup[] {
  const byMatchday = new Map<number, FixtureCard[]>();
  for (const fixture of fixtures) {
    byMatchday.set(fixture.matchday, [...(byMatchday.get(fixture.matchday) ?? []), fixture]);
  }
  return [...byMatchday.entries()]
    .sort(([a], [b]) => a - b)
    .map(([matchday, group]) => ({
      matchday,
      fixtures: group.toSorted((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.id - b.id),
    }));
}
