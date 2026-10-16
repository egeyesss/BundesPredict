import { describe, expect, it } from "vitest";

import { fixtureDetails } from "@/lib/api/mocks/data";

import { HEATMAP_SIZE, cleanSheets, formatMarketChange, heatShade, marketRows, scoreGrid } from "./markets";

const markets = fixtureDetails["803"].markets;

describe("scoreGrid", () => {
  it("keeps 0 to 5 goals a side with home goals as rows", () => {
    const grid = scoreGrid(markets);
    expect(grid).toHaveLength(HEATMAP_SIZE);
    expect(grid.every((row) => row.length === HEATMAP_SIZE)).toBe(true);
    expect(grid[2][1]).toBe(markets.score_grid[2][1]);
  });
});

describe("cleanSheets", () => {
  it("adds up the column or row where the other side scores nothing", () => {
    const grid = markets.score_grid;
    const awayScoresNothing = grid.reduce((sum, row) => sum + row[0], 0);
    const homeScoresNothing = grid[0].reduce((sum, p) => sum + p, 0);
    expect(cleanSheets(markets)).toEqual({ home: awayScoresNothing, away: homeScoresNothing });
  });
});

describe("marketRows", () => {
  it("lists the five markets with the new and the previous value", () => {
    const rows = marketRows(markets, markets, "Dortmund", "Hoffenheim");
    expect(rows.map((row) => row.name)).toEqual([
      "Over 2.5 goals",
      "Under 2.5 goals",
      "Both teams score",
      "Dortmund clean sheet",
      "Hoffenheim clean sheet",
    ]);
    expect(rows[0]).toMatchObject({ now: markets.p_over_2_5, before: markets.p_over_2_5 });
    expect(rows[3].sub).toBe("Hoffenheim don't score");
  });
});

describe("formatMarketChange", () => {
  it("uses neutral arrows with a real minus sign", () => {
    expect(formatMarketChange(0.55, 0.5)).toBe("▲ +5.0");
    expect(formatMarketChange(0.45, 0.5)).toBe("▼ −5.0");
  });

  it("says no change under half a point", () => {
    expect(formatMarketChange(0.5, 0.503)).toBe("no change");
  });
});

describe("heatShade", () => {
  it("mixes from the card surface to near white in OKLab", () => {
    expect(heatShade(0)).toBe("color-mix(in oklab, #F4F4F5 0%, #1B1B1F)");
    expect(heatShade(1)).toBe("color-mix(in oklab, #F4F4F5 100%, #1B1B1F)");
  });
});
