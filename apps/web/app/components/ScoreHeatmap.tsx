import type { Markets } from "@/lib/api";

// The engine's grid runs to 10 goals a side, but 0-5 carries essentially all
// of the mass for football lambdas; the tail would render as invisible cells.
const SHOWN_GOALS = 6;

function pct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/** Correct-score heatmap of the served distribution, home goals down the side. */
export default function ScoreHeatmap({ markets }: { markets: Markets }) {
  const grid = markets.score_grid;
  const shown = grid
    .slice(0, SHOWN_GOALS)
    .map((row) => row.slice(0, SHOWN_GOALS));
  const max = Math.max(...shown.flat());
  const [topHome, topAway] = [
    markets.top_scores[0]?.home,
    markets.top_scores[0]?.away,
  ];

  return (
    <div className="inline-block">
      <div
        className="grid gap-px text-[10px]"
        style={{
          gridTemplateColumns: `auto repeat(${SHOWN_GOALS}, minmax(0, 1fr))`,
        }}
      >
        <div />
        {shown[0].map((_, away) => (
          <div
            key={`col-${away}`}
            className="pb-1 text-center text-zinc-500 dark:text-zinc-400"
          >
            {away}
          </div>
        ))}
        {shown.map((row, home) => (
          <div key={`row-${home}`} className="contents">
            <div className="flex items-center pr-1.5 text-zinc-500 dark:text-zinc-400">
              {home}
            </div>
            {row.map((p, away) => {
              const isTop = home === topHome && away === topAway;
              return (
                <div
                  key={`${home}-${away}`}
                  title={`${home}–${away}: ${pct(p)}`}
                  className={`flex aspect-square w-9 items-center justify-center rounded-sm tabular-nums ${
                    isTop ? "ring-2 ring-red-600 dark:ring-red-500" : ""
                  } ${
                    p / max > 0.55
                      ? "text-white"
                      : "text-zinc-600 dark:text-zinc-300"
                  }`}
                  style={{
                    // Single-hue ramp; per-cell alpha needs an inline style.
                    backgroundColor: `rgba(220, 38, 38, ${(0.9 * p) / max})`,
                  }}
                >
                  {p >= 0.005 ? (p * 100).toFixed(0) : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-zinc-500 dark:text-zinc-400">
        home goals ↓ · away goals → · cell = % chance of that exact score
      </p>
    </div>
  );
}
