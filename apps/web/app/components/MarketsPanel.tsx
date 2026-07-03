import type { Markets } from "@/lib/api";

function pct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/** Secondary markets sliced from the same distribution: totals, BTTS, scorelines. */
export default function MarketsPanel({ markets }: { markets: Markets }) {
  const stats = [
    { label: "Over 2.5", value: pct(markets.p_over_2_5) },
    { label: "Under 2.5", value: pct(markets.p_under_2_5) },
    { label: "Both teams score", value: pct(markets.p_btts) },
    {
      label: "Expected goals",
      value: `${markets.exp_home_goals.toFixed(2)} – ${markets.exp_away_goals.toFixed(2)}`,
    },
  ];

  return (
    <div className="space-y-3 text-xs">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {stats.map(({ label, value }) => (
          <div
            key={label}
            className="rounded-lg border border-black/10 bg-white px-3 py-2 dark:border-white/10 dark:bg-zinc-900"
          >
            <dt className="text-zinc-500 dark:text-zinc-400">{label}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <div>
        <span className="text-zinc-500 dark:text-zinc-400">
          Most likely scores:{" "}
        </span>
        {markets.top_scores.map((s, i) => (
          <span key={i} className="text-zinc-700 dark:text-zinc-300">
            {i > 0 && " · "}
            <span className="font-medium tabular-nums">
              {s.home}–{s.away}
            </span>{" "}
            <span className="tabular-nums text-zinc-500 dark:text-zinc-400">
              ({pct(s.p)})
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
