/** Home win, draw, away win: indices 0, 1, 2 everywhere in this file. */
export type OutcomeTriple = readonly [number, number, number];
export type OddsRole = "win" | "draw" | "lose";

export type DisplayOdds = {
  /** Outcome indices from most to least likely. */
  order: readonly [number, number, number];
  decimals: number;
  /** Integer counts of 10^-decimals percent; they sum to exactly 100 percent. */
  units: readonly [number, number, number];
  /** What to print before the % sign, with tiny values shown as "<1". */
  text: readonly [string, string, string];
  roles: readonly [OddsRole, OddsRole, OddsRole];
  lead: 0 | 1 | 2;
  /** True when two decimals still tied and the trailing values were nudged down by 0.01. */
  nudged: boolean;
};

const DRAW = 1;

function rankOutcomes(probs: OutcomeTriple, xg: readonly [number, number]): [number, number, number] {
  const favouriteTeamOnTie = xg[0] >= xg[1] ? 0 : 2;
  return ([0, 1, 2] as const).toSorted((a, b) => {
    if (probs[a] !== probs[b]) return probs[b] - probs[a];
    const aIsTeam = a !== DRAW;
    const bIsTeam = b !== DRAW;
    if (aIsTeam !== bIsTeam) return aIsTeam ? -1 : 1;
    return a === favouriteTeamOnTie ? -1 : 1;
  }) as [number, number, number];
}

function largestRemainder(probs: OutcomeTriple, decimals: number, order: readonly number[]): [number, number, number] {
  const total = 100 * 10 ** decimals;
  const scaled = probs.map((p) => Math.round(p * total * 1e6) / 1e6);
  const floors = scaled.map(Math.floor);
  let left = total - floors.reduce((sum, floor) => sum + floor, 0);
  const byRemainder = [0, 1, 2].toSorted(
    (a, b) => scaled[b] - floors[b] - (scaled[a] - floors[a]) || order.indexOf(a) - order.indexOf(b),
  );
  for (const index of byRemainder) {
    if (left-- > 0) floors[index] += 1;
  }
  return floors as [number, number, number];
}

function present(
  units: [number, number, number],
  decimals: number,
  order: [number, number, number],
  nudged: boolean,
): DisplayOdds {
  const scale = 10 ** decimals;
  const text = units.map((unit) =>
    unit === 0 ? `<${decimals ? (1 / scale).toFixed(decimals) : "1"}` : (unit / scale).toFixed(decimals),
  ) as [string, string, string];
  const favouriteTeam = order.find((index) => index !== DRAW);
  const roles = [0, 1, 2].map((index): OddsRole => (index === DRAW ? "draw" : index === favouriteTeam ? "win" : "lose")) as [
    OddsRole,
    OddsRole,
    OddsRole,
  ];
  return { order, decimals, units, text, roles, lead: order[0] as 0 | 1 | 2, nudged };
}

/**
 * Rounds three outcome probabilities for display. Uses the fewest decimals
 * (0, 1 or 2) that keep all three values distinct, largest-remainder rounding
 * so they sum to 100, and breaks exact ties as a team over the draw, then by
 * expected goals, then home.
 */
export function displayOdds(probs: OutcomeTriple, xg: readonly [number, number]): DisplayOdds {
  const order = rankOutcomes(probs, xg);
  const distinct = (units: readonly number[]) => units[order[0]] > units[order[1]] && units[order[1]] > units[order[2]];

  for (const decimals of [0, 1, 2]) {
    const units = largestRemainder(probs, decimals, order);
    if (distinct(units)) return present(units, decimals, order, false);
  }

  const units = largestRemainder(probs, 2, order);
  for (let rank = 1; rank < 3; rank++) {
    if (units[order[rank]] >= units[order[rank - 1]]) units[order[rank]] = units[order[rank - 1]] - 1;
  }
  units[order[0]] += 10000 - units.reduce((sum, unit) => sum + unit, 0);
  return present(units, 2, order, true);
}
