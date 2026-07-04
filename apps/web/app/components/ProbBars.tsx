import type { Markets } from "@/lib/api";

const OUTCOMES = [
  { key: "p_home", label: "Home win" },
  { key: "p_draw", label: "Draw" },
  { key: "p_away", label: "Away win" },
] as const;

function pct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/**
 * The 1X2 view: one row per outcome, baseline bar above adjusted bar so the
 * shift the adjustments caused is readable at a glance. Without an adjusted
 * distribution it renders the baseline alone.
 */
export default function ProbBars({
  baseline,
  adjusted,
}: {
  baseline: Markets;
  adjusted: Markets | null;
}) {
  return (
    <div className="space-y-3">
      {OUTCOMES.map(({ key, label }) => {
        const base = baseline[key];
        const adj = adjusted?.[key];
        const delta = adj !== undefined ? adj - base : null;
        return (
          <div key={key}>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {label}
              </span>
              <span className="tabular-nums text-zinc-500 dark:text-zinc-400">
                {adj !== undefined ? (
                  <>
                    {pct(base)} →{" "}
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {pct(adj)}
                    </span>
                    {delta !== null && Math.abs(delta) >= 0.0005 && (
                      <span
                        className={
                          delta > 0
                            ? "ml-1 text-emerald-600 dark:text-emerald-400"
                            : "ml-1 text-red-600 dark:text-red-400"
                        }
                      >
                        ({delta > 0 ? "+" : ""}
                        {(delta * 100).toFixed(1)})
                      </span>
                    )}
                  </>
                ) : (
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {pct(base)}
                  </span>
                )}
              </span>
            </div>
            <div className="space-y-1">
              <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                <div
                  className="h-full rounded-full bg-zinc-400 dark:bg-zinc-500"
                  style={{ width: pct(base) }}
                />
              </div>
              {adj !== undefined && (
                <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                  <div
                    className="h-full rounded-full bg-red-600 dark:bg-red-500"
                    style={{ width: pct(adj) }}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
      {adjusted !== null && (
        <div className="flex gap-4 pt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-4 rounded-full bg-zinc-400 dark:bg-zinc-500" />
            baseline
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-4 rounded-full bg-red-600 dark:bg-red-500" />
            adjusted
          </span>
        </div>
      )}
    </div>
  );
}
