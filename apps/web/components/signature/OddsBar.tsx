import { displayOdds, type OutcomeTriple } from "@/lib/odds";
import { cn } from "@/lib/utils";

import "./bars.css";

export type OddsBarProps = {
  home: string;
  away: string;
  /** Home win, draw, away win as probabilities in [0, 1]. */
  probs: OutcomeTriple;
  /** Expected goals, only used to break exact ties in who leads. */
  expectedGoals: readonly [number, number];
  className?: string;
};

const LABEL_BASE = "text-bp-text-muted data-[lead]:font-semibold data-[lead]:text-bp-text";

/**
 * A 1X2 bar with a text value under every segment. Segment widths use the true
 * probabilities; the printed numbers use the rounding rules in `displayOdds`.
 */
export function OddsBar({ home, away, probs, expectedGoals, className }: OddsBarProps) {
  const odds = displayOdds(probs, expectedGoals);
  const names = [home, "draw", away] as const;
  const summary = names.map((name, index) => `${name} ${odds.text[index]}%`).join(", ");
  const segment = (index: 0 | 1 | 2) => ({
    "data-role": odds.roles[index],
    "data-lead": odds.lead === index ? "" : undefined,
  });

  return (
    <div className={className}>
      <div className="odds-bar" role="img" aria-label={summary}>
        {([0, 1, 2] as const).map((index) => (
          <i key={index} data-segment style={{ flexGrow: probs[index] }} {...segment(index)} />
        ))}
      </div>
      <div className="mt-1 grid grid-cols-[1fr_auto_1fr] gap-2 font-mono text-xs font-medium tabular-nums" aria-hidden="true">
        <span {...segment(0)} className={cn(LABEL_BASE, "data-[lead]:data-[role=win]:text-odds-win-text")}>
          {odds.text[0]}%
        </span>
        <span {...segment(1)} className={cn(LABEL_BASE, "text-center data-[lead]:data-[role=draw]:text-odds-draw-lead")}>
          Draw {odds.text[1]}%
        </span>
        <span {...segment(2)} className={cn(LABEL_BASE, "text-right data-[lead]:data-[role=win]:text-odds-win-text")}>
          {odds.text[2]}%
        </span>
      </div>
    </div>
  );
}
