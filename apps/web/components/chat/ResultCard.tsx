"use client";

import { AdjustmentChip } from "@/components/signature/AdjustmentChip";
import { ProbabilityBars } from "@/components/signature/ProbabilityBars";
import type { PredictResponse, Team } from "@/lib/api/types";
import { shortName } from "@/lib/chat/teams";

import { MoreMarkets } from "./MoreMarkets";

type ResultCardProps = {
  result: PredictResponse;
  teams: readonly Team[] | undefined;
};

/** The answer's numbers: the model's odds, the odds with the news applied, why they moved, and the wider markets. */
export function ResultCard({ result, teams }: ResultCardProps) {
  const { baseline, adjusted, adjustments } = result;
  if (baseline === null) return null;

  const home = shortName(teams, result.home ?? "Home");
  const away = shortName(teams, result.away ?? "Away");
  const withNews = adjusted !== null && adjustments.length > 0;
  const title = withNews ? "Odds with your news" : "Model odds";

  return (
    <section
      aria-label={withNews ? "Updated odds" : title}
      className="grid min-w-0 gap-3.5 rounded-xl border border-bp-border bg-bp-surface-1 px-[18px] py-4"
    >
      <h2 className="font-mono text-xs font-normal tracking-[0.08em] text-bp-text-muted uppercase">{title}</h2>

      <div data-tour="result">
        <ProbabilityBars home={home} away={away} baseline={baseline} adjusted={withNews ? adjusted : undefined} />
      </div>

      {withNews && (
        <ul data-tour="chips" className="flex list-none flex-wrap gap-2 p-0">
          {adjustments.map((adjustment, index) => (
            <li key={`${adjustment.factor}-${adjustment.target}-${index}`} className="max-w-full">
              <AdjustmentChip adjustment={adjustment} homeName={home} awayName={away} />
            </li>
          ))}
        </ul>
      )}

      {withNews && (
        <p className="text-xs text-bp-text-muted">
          The model computes the odds. The agent only moves expected goals, and every adjustment is capped.
        </p>
      )}

      <MoreMarkets home={home} away={away} baseline={baseline} adjusted={withNews ? adjusted : null} />
    </section>
  );
}
