import { describe, expect, it } from "vitest";

import { displayOdds, type OutcomeTriple } from "./odds";

type Case = {
  name: string;
  probs: OutcomeTriple;
  xg: readonly [number, number];
  text: [string, string, string];
  decimals: number;
  roles: [string, string, string];
  lead: 0 | 1 | 2;
  nudged: boolean;
};

const CASES: Case[] = [
  { name: "clear home favourite", probs: [0.6421, 0.1902, 0.1677], xg: [2.61, 1.14], text: ["64", "19", "17"], decimals: 0, roles: ["win", "draw", "lose"], lead: 0, nudged: false },
  { name: "away favourite needs one decimal", probs: [0.2618, 0.2544, 0.4838], xg: [1.11, 1.74], text: ["26.2", "25.4", "48.4"], decimals: 1, roles: ["lose", "draw", "win"], lead: 2, nudged: false },
  { name: "draw leads by 0.03 points", probs: [0.3349, 0.3352, 0.3299], xg: [1.18, 1.16], text: ["33.49", "33.52", "32.99"], decimals: 2, roles: ["win", "draw", "lose"], lead: 1, nudged: false },
  { name: "teams 0.02 points apart", probs: [0.3645, 0.2712, 0.3643], xg: [1.31, 1.3], text: ["37", "27", "36"], decimals: 0, roles: ["win", "draw", "lose"], lead: 0, nudged: false },
  { name: "exact tie goes to higher xG (away)", probs: [0.38, 0.24, 0.38], xg: [1.37, 1.42], text: ["37.99", "24.00", "38.01"], decimals: 2, roles: ["lose", "draw", "win"], lead: 2, nudged: true },
  { name: "exact tie with equal xG goes home", probs: [0.38, 0.24, 0.38], xg: [1.4, 1.4], text: ["38.01", "24.00", "37.99"], decimals: 2, roles: ["win", "draw", "lose"], lead: 0, nudged: true },
  { name: "three-way near tie", probs: [0.33333, 0.33334, 0.33333], xg: [1.2, 1.2], text: ["33.33", "33.35", "33.32"], decimals: 2, roles: ["win", "draw", "lose"], lead: 1, nudged: true },
  { name: "long shot under one percent", probs: [0.968, 0.028, 0.004], xg: [3.1, 0.4], text: ["97", "3", "<1"], decimals: 0, roles: ["win", "draw", "lose"], lead: 0, nudged: false },
  { name: "would round to 101 if naive", probs: [0.335, 0.335, 0.33], xg: [1.3, 1.25], text: ["33.51", "33.49", "33.00"], decimals: 2, roles: ["win", "draw", "lose"], lead: 0, nudged: true },
];

describe("displayOdds", () => {
  it.each(CASES)("$name", ({ probs, xg, text, decimals, roles, lead, nudged }) => {
    const odds = displayOdds(probs, xg);
    expect(odds.text).toEqual(text);
    expect(odds.decimals).toBe(decimals);
    expect(odds.roles).toEqual(roles);
    expect(odds.lead).toBe(lead);
    expect(odds.nudged).toBe(nudged);
  });

  it("always shows three distinct values that sum to exactly 100", () => {
    for (const { probs, xg } of CASES) {
      const odds = displayOdds(probs, xg);
      const scale = 10 ** odds.decimals;
      expect(odds.units.reduce((sum, unit) => sum + unit, 0)).toBe(100 * scale);
      expect(new Set(odds.units).size).toBe(3);
    }
  });

  it("ranks by full-precision probability, so the leader is the largest input", () => {
    const odds = displayOdds([0.2, 0.3, 0.5], [1, 2]);
    expect(odds.order).toEqual([2, 1, 0]);
    expect(odds.lead).toBe(2);
  });
});
