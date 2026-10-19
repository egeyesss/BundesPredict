import { describe, expect, it } from "vitest";

import { fixtureCards } from "@/lib/api/mocks/data";

import { formatKickoff, groupByMatchday, seasonLabel } from "./matchday";

describe("formatKickoff", () => {
  const kickoff = "2026-10-16T18:30:00Z";

  it("prints the weekday and the time in the given timezone", () => {
    expect(formatKickoff(kickoff, { timeZone: "America/Toronto", locale: "en-US" })).toMatch(/^Fri,? 2:30 PM$/);
    expect(formatKickoff(kickoff, { timeZone: "Europe/Berlin", locale: "en-US" })).toMatch(/^Fri,? 8:30 PM$/);
  });

  it("rolls the weekday over with the timezone", () => {
    const lateFriday = "2026-10-16T23:30:00Z";
    expect(formatKickoff(lateFriday, { timeZone: "Europe/Berlin", locale: "en-US" })).toMatch(/^Sat,? 1:30 AM$/);
  });
});

describe("seasonLabel", () => {
  it("writes the season the way the league does", () => {
    expect(seasonLabel("2026-27")).toBe("2026/27");
  });

  it("expands the four-digit form Django stores", () => {
    expect(seasonLabel("2627")).toBe("2026/27");
    expect(seasonLabel("9900")).toBe("1999/00");
  });

  it("labels every recorded fixture with the stored season format", () => {
    expect(fixtureCards.map((fixture) => fixture.season)).toEqual(fixtureCards.map(() => "2627"));
  });
});

describe("groupByMatchday", () => {
  it("keeps one group per matchday in kickoff order", () => {
    const groups = groupByMatchday(fixtureCards);
    expect(groups).toHaveLength(1);
    expect(groups[0].matchday).toBe(8);
    expect(groups[0].fixtures.map((fixture) => fixture.id)).toEqual(fixtureCards.map((fixture) => fixture.id));
  });

  it("splits a week that spans two matchdays and sorts them", () => {
    const earlier = { ...fixtureCards[0], id: 1, matchday: 7, kickoff_utc: "2026-10-10T13:30:00Z" };
    const later = { ...fixtureCards[1], id: 2, matchday: 8, kickoff_utc: "2026-10-17T13:30:00Z" };
    const groups = groupByMatchday([later, earlier]);
    expect(groups.map((group) => group.matchday)).toEqual([7, 8]);
    expect(groups[0].fixtures[0].id).toBe(1);
  });

  it("returns no groups for no fixtures", () => {
    expect(groupByMatchday([])).toEqual([]);
  });
});
