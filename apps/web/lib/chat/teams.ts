import type { Team } from "@/lib/api/types";

const normalise = (name: string) => name.trim().toLowerCase();

export function findTeam(teams: readonly Team[] | undefined, name: string): Team | undefined {
  const wanted = normalise(name);
  return teams?.find((team) => normalise(team.name) === wanted || normalise(team.short_name) === wanted);
}

export function shortName(teams: readonly Team[] | undefined, name: string): string {
  return findTeam(teams, name)?.short_name ?? name;
}

type NamedSides = { home: { name: string }; away: { name: string } };

/** Whether the agent's answer is about the match the chat is pinned to. */
export function resultMatchesFixture(result: { home: string | null; away: string | null }, fixture: NamedSides): boolean {
  if (result.home === null || result.away === null) return false;
  return normalise(result.home) === normalise(fixture.home.name) && normalise(result.away) === normalise(fixture.away.name);
}
