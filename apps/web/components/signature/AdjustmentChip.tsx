"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Mirrors the API's applied adjustment: what the agent asked for next to what the engine allowed. */
export type AppliedAdjustment = {
  factor: string;
  team: string | null;
  target: string;
  requested_magnitude_xg: number;
  effective_magnitude_xg: number;
  confidence: string;
  rationale: string;
};

const MATCH_LEVEL_TARGETS: Record<string, string> = {
  home_adv: "home advantage",
  cards_rate: "cards rate",
  pen_rate: "penalty rate",
};

const CONFIDENCE_WORDS: Record<string, string> = { med: "medium" };

/** "home_attack" becomes "Bayern attack" when the club names are known. */
export function targetLabel(target: string, homeName?: string, awayName?: string): string {
  if (target in MATCH_LEVEL_TARGETS) return MATCH_LEVEL_TARGETS[target];
  const [side, ...rest] = target.split("_");
  const area = rest.join(" ");
  if (side === "home" || side === "away") return `${side === "home" ? (homeName ?? "home") : (awayName ?? "away")} ${area}`;
  return target.replaceAll("_", " ");
}

const signed = (value: number) => `${value < 0 ? "−" : "+"}${Math.abs(value).toFixed(2)}`;
const differs = (requested: number, effective: number) => Math.abs(requested - effective) >= 0.005;

export type AdjustmentChipProps = {
  adjustment: AppliedAdjustment;
  homeName?: string;
  awayName?: string;
  className?: string;
};

/** One agent adjustment in the model's mono voice; the rationale opens on hover or focus. */
export function AdjustmentChip({ adjustment, homeName, awayName, className }: AdjustmentChipProps) {
  const { factor, target, requested_magnitude_xg: requested, effective_magnitude_xg: effective, confidence, rationale } = adjustment;
  const capped = differs(requested, effective);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          tabIndex={0}
          className={cn(
            "grid max-w-full cursor-default gap-0.5 rounded-[var(--bp-radius-chip)] border border-bp-border bg-bp-bg px-2.5 py-2 font-mono text-xs leading-[1.45] outline-offset-2",
            className,
          )}
        >
          <span className="text-bp-text">
            {factor} {"·"} {targetLabel(target, homeName, awayName)}
          </span>
          <span className="text-bp-text-muted">
            {capped ? (
              <>
                asked {signed(requested)} xG {"→"} <span className="text-bp-red-text">capped at {signed(effective)}</span>
              </>
            ) : (
              <>{signed(effective)} xG</>
            )}{" "}
            {"·"} confidence {CONFIDENCE_WORDS[confidence] ?? confidence}
          </span>
          <span className="sr-only">{rationale}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[min(20rem,calc(100vw-2rem))]">
        {rationale}
      </TooltipContent>
    </Tooltip>
  );
}
