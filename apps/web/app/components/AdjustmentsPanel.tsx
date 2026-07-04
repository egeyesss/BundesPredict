import type { AppliedAdjustment } from "@/lib/api";

const CONFIDENCE_STYLE: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  medium: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

function signed(x: number): string {
  return `${x > 0 ? "+" : ""}${x.toFixed(2)}`;
}

/**
 * The "show your work" view: every adjustment the agent applied, as a chip
 * with the factor, the expected-goals delta actually applied (and the request,
 * when the engine clamped it), the confidence, and the one-line rationale.
 */
export default function AdjustmentsPanel({
  adjustments,
}: {
  adjustments: AppliedAdjustment[];
}) {
  return (
    <ul className="space-y-2">
      {adjustments.map((adj, i) => {
        const clamped =
          adj.requested_magnitude_xg !== adj.effective_magnitude_xg;
        return (
          <li
            key={i}
            className="rounded-lg border border-black/10 bg-white px-3 py-2 text-xs dark:border-white/10 dark:bg-zinc-900"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-zinc-900 dark:text-zinc-100">
                {adj.factor.replaceAll("_", " ")}
              </span>
              <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {adj.target.replaceAll("_", " ")} {signed(adj.effective_magnitude_xg)}{" "}
                xG
              </span>
              {clamped && (
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] text-red-700 dark:bg-red-950 dark:text-red-300">
                  clamped from {signed(adj.requested_magnitude_xg)}
                </span>
              )}
              <span
                className={`rounded px-1.5 py-0.5 text-[11px] ${
                  CONFIDENCE_STYLE[adj.confidence] ?? CONFIDENCE_STYLE.low
                }`}
              >
                {adj.confidence}
              </span>
            </div>
            <p className="mt-1 text-zinc-600 dark:text-zinc-400">
              {adj.rationale}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
