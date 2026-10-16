import { describe, expect, it } from "vitest";

import { teams } from "@/lib/api/mocks/data";

import { findTeam, resultMatchesFixture, shortName } from "./teams";

describe("team lookup", () => {
  it("finds a club by the full name the agent uses", () => {
    expect(findTeam(teams, "Borussia Dortmund")?.code).toBe("BVB");
  });

  it("is not thrown by case or spacing differences", () => {
    expect(findTeam(teams, " borussia dortmund ")?.code).toBe("BVB");
  });

  it("returns the short name, or the original text for a club it does not know", () => {
    expect(shortName(teams, "TSG 1899 Hoffenheim")).toBe("Hoffenheim");
    expect(shortName(teams, "Real Madrid")).toBe("Real Madrid");
    expect(shortName(undefined, "Real Madrid")).toBe("Real Madrid");
  });
});

describe("resultMatchesFixture", () => {
  const dortmund = { home: { name: "Borussia Dortmund" }, away: { name: "TSG 1899 Hoffenheim" } };

  it("is true when the agent answered about the pinned match", () => {
    expect(resultMatchesFixture({ home: "Borussia Dortmund", away: "TSG 1899 Hoffenheim" }, dortmund)).toBe(true);
    expect(resultMatchesFixture({ home: "borussia dortmund", away: "tsg 1899 hoffenheim" }, dortmund)).toBe(true);
  });

  it("is false for another match or an answer with no teams", () => {
    expect(resultMatchesFixture({ home: "Bayern Munich", away: "1.FSV Mainz 05" }, dortmund)).toBe(false);
    expect(resultMatchesFixture({ home: null, away: null }, dortmund)).toBe(false);
  });
});
