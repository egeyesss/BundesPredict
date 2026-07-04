import type { PredictResponse } from "@/lib/api";
import AdjustmentsPanel from "./AdjustmentsPanel";
import Explanation from "./Explanation";
import MarketsPanel from "./MarketsPanel";
import ProbBars from "./ProbBars";
import ScoreHeatmap from "./ScoreHeatmap";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {title}
      </h3>
      {children}
    </section>
  );
}

/** One full answer: explanation, 1X2 shift, adjustments, heatmap, markets. */
export default function ResultCard({ result }: { result: PredictResponse }) {
  const served = result.adjusted ?? result.baseline;

  // No fixture was predicted (a clarification, an unknown team...): words only.
  if (result.baseline === null || served === null) {
    return <Explanation text={result.explanation} />;
  }

  return (
    <div className="space-y-5">
      <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
        {result.home} <span className="font-normal text-zinc-400">vs</span>{" "}
        {result.away}
      </h2>

      <Explanation text={result.explanation} />

      <Section title="Match odds">
        <ProbBars baseline={result.baseline} adjusted={result.adjusted} />
      </Section>

      {result.adjustments.length > 0 && (
        <Section title="Applied adjustments">
          <AdjustmentsPanel adjustments={result.adjustments} />
        </Section>
      )}

      <Section
        title={
          result.adjusted !== null
            ? "Scoreline heatmap (adjusted)"
            : "Scoreline heatmap"
        }
      >
        <ScoreHeatmap markets={served} />
      </Section>

      <Section title="Markets">
        <MarketsPanel markets={served} />
      </Section>
    </div>
  );
}
