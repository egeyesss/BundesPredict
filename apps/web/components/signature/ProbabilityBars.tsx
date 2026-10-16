"use client";

import { useEffect, useState } from "react";

import { displayOdds, formatPointChange, type OutcomeTriple } from "@/lib/odds";
import { cn } from "@/lib/utils";

import { OddsBar } from "./OddsBar";
import { useReducedMotion } from "./reduced-motion";

export type OutcomeMarkets = {
  p_home: number;
  p_draw: number;
  p_away: number;
  exp_home_goals: number;
  exp_away_goals: number;
};

export type ProbabilityBarsProps = {
  home: string;
  away: string;
  baseline: OutcomeMarkets;
  /** When present, a second bar tweens from the baseline to these values and the changes are listed. */
  adjusted?: OutcomeMarkets;
  baselineLabel?: string;
  adjustedLabel?: string;
  className?: string;
};

const probsOf = (markets: OutcomeMarkets): OutcomeTriple => [markets.p_home, markets.p_draw, markets.p_away];
const goalsOf = (markets: OutcomeMarkets) => [markets.exp_home_goals, markets.exp_away_goals] as const;
const xg = (markets: OutcomeMarkets) => goalsOf(markets).map((goals) => goals.toFixed(2)).join(" – ");

const ARROW = { up: "▲", down: "▼", none: "" } as const;

/**
 * The model's odds, and when the agent applied news, the odds with it: the second
 * bar tweens from the baseline (400ms, ease-out) and each outcome shows its change
 * in points. Arrows stay neutral so green and red only ever mean win and lose.
 */
export function ProbabilityBars({
  home,
  away,
  baseline,
  adjusted,
  baselineLabel = "Model only",
  adjustedLabel = "With your news",
  className,
}: ProbabilityBarsProps) {
  const reducedMotion = useReducedMotion(false);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!adjusted) return;
    let inner = 0;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => setRevealed(true));
    });
    return () => {
      cancelAnimationFrame(outer);
      cancelAnimationFrame(inner);
    };
  }, [adjusted]);

  const shown = adjusted && (reducedMotion || revealed) ? adjusted : baseline;
  const baselineProbs = probsOf(baseline);

  return (
    <div className={cn("grid gap-3.5", className)}>
      <div className="grid gap-2.5">
        <Row label={baselineLabel}>
          <OddsBar home={home} away={away} probs={baselineProbs} expectedGoals={goalsOf(baseline)} />
        </Row>
        {adjusted && (
          <Row label={adjustedLabel}>
            <OddsBar home={home} away={away} probs={probsOf(shown)} expectedGoals={goalsOf(adjusted)} />
          </Row>
        )}
      </div>

      {adjusted && <DeltaTiles home={home} away={away} baseline={baseline} adjusted={adjusted} />}

      <p className="font-mono text-xs text-bp-text-muted tabular-nums">
        xG {xg(baseline)}
        {adjusted && <> {"→"} {xg(adjusted)}</>}
      </p>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid items-center gap-1 sm:grid-cols-[110px_minmax(0,1fr)] sm:gap-3">
      <span className="font-mono text-xs text-bp-text-muted">{label}</span>
      {children}
    </div>
  );
}

function DeltaTiles({
  home,
  away,
  baseline,
  adjusted,
}: {
  home: string;
  away: string;
  baseline: OutcomeMarkets;
  adjusted: OutcomeMarkets;
}) {
  const before = probsOf(baseline);
  const after = probsOf(adjusted);
  const odds = displayOdds(after, goalsOf(adjusted));
  const names = [home, "Draw", away] as const;

  return (
    <div className="grid grid-cols-3 gap-2">
      {([0, 1, 2] as const).map((index) => {
        const change = formatPointChange(after[index] - before[index]);
        const isLead = odds.lead === index;
        return (
          <div key={index} data-testid="delta" className="grid min-w-0 gap-0.5 rounded-lg border border-bp-border bg-bp-bg px-2.5 py-2.5 sm:px-3">
            <small className="truncate font-mono text-[11px] tracking-wider text-bp-text-muted uppercase">{names[index]}</small>
            <strong
              className={cn(
                "font-display text-[26px] leading-none font-bold tabular-nums",
                isLead ? (odds.roles[index] === "win" ? "text-odds-win-text" : "text-odds-draw-lead") : "text-bp-text-muted",
              )}
            >
              {odds.text[index]}%
            </strong>
            <span className="font-mono text-[11px] font-medium whitespace-nowrap text-bp-text-muted tabular-nums sm:text-xs">
              {change.direction === "none" ? "no change" : `${ARROW[change.direction]} ${change.text} pts`}
            </span>
          </div>
        );
      })}
    </div>
  );
}
