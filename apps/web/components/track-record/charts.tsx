"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { axisTicks, rpsDomain, score, type CalibrationBin, type MatchdayRow } from "./format";
import "./track-record.css";

const COLORS = {
  model: "var(--series-model)",
  market: "var(--series-market)",
  base: "var(--series-base)",
};

/** Width of the element in CSS pixels; 0 until the first measurement. */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    setWidth(node.clientWidth);
    const observer = new ResizeObserver(() => setWidth(node.clientWidth));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

type TipState = { x: number; y: number; title: string; rows: { color: string; label: string; value: string }[] } | null;

function Tip({ tip }: { tip: TipState }) {
  if (!tip) return null;
  return (
    <div
      role="presentation"
      className="pointer-events-none absolute z-10 min-w-[150px] -translate-y-full rounded-lg border border-bp-border bg-bp-surface-2 px-2.5 py-2 text-xs shadow-[0_8px_24px_rgb(0_0_0/0.5)]"
      style={{ left: tip.x, top: tip.y - 10, transform: "translate(-50%, -100%)" }}
    >
      <div className="mb-1 font-mono text-[11px] font-medium text-bp-text-muted">{tip.title}</div>
      {tip.rows.map((row) => (
        <div key={row.label} className="grid grid-cols-[10px_1fr_auto] items-center gap-2">
          <i className="size-2 rounded-full" style={{ background: row.color }} />
          <span>{row.label}</span>
          <b className="font-mono font-medium">{row.value}</b>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[13px] text-bp-text-muted">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <i className="h-[3px] w-3.5 rounded-sm" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

/** A titled card with a "Show as table" switch; the table always carries the same numbers as the chart. */
export function ChartCard({
  title,
  description,
  legend,
  chart,
  table,
  note,
  className,
}: {
  title: string;
  description: string;
  legend?: ReactNode;
  chart: ReactNode;
  table: ReactNode;
  note?: ReactNode;
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section aria-label={title} className={cn("grid min-w-0 gap-3.5 rounded-xl border border-bp-border bg-bp-surface-1 p-5", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2.5">
        <div className="grid min-w-[240px] flex-1 gap-1">
          <h3 className="font-display text-xl leading-tight font-semibold tracking-[0.02em]">{title}</h3>
          <p className="max-w-[62ch] text-sm text-bp-text-muted">{description}</p>
        </div>
        <button
          type="button"
          aria-pressed={showTable}
          onClick={() => setShowTable((value) => !value)}
          className="touch-target rounded-md border border-bp-border bg-bp-surface-2 px-2.5 py-1.5 font-mono text-xs font-medium text-bp-text-muted hover:text-bp-text"
        >
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </div>
      {legend}
      {showTable ? <div className="overflow-x-auto">{table}</div> : chart}
      {note}
    </section>
  );
}

export function DataTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full border-collapse text-[13px] tabular-nums">
      <thead>
        <tr>
          {head.map((cell) => (
            <th key={cell} scope="col" className="border-b border-bp-border px-2 py-1.5 text-left font-mono text-[11px] font-medium tracking-[0.06em] text-bp-text-muted uppercase">
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((cells, index) => (
          <tr key={index}>
            {cells.map((cell, cellIndex) => (
              <td key={cellIndex} className="border-b border-bp-border px-2 py-1.5">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const LINE_SERIES = [
  { key: "rps", label: "Model", color: COLORS.model },
  { key: "bookmaker_rps", label: "Closing market", color: COLORS.market },
  { key: "base_rate_rps", label: "Base rate", color: COLORS.base },
] as const;

/** Average RPS per matchday for the model, the closing market and the base rate, with direct labels. */
export function RpsLineChart({ rows }: { rows: MatchdayRow[] }) {
  const { ref, width } = useWidth();
  const [tip, setTip] = useState<TipState>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const height = 280;
  const single = rows.length === 1;
  const margin = { left: 48, right: width < 480 || single ? 12 : 100, top: 28, bottom: 34 };
  const { low, high } = rpsDomain(rows);
  const x = (index: number) => margin.left + (single ? Math.min(120, (width - margin.left - margin.right) / 3) : (index * (width - margin.left - margin.right)) / (rows.length - 1));
  const y = (value: number) => margin.top + ((high - value) * (height - margin.top - margin.bottom)) / (high - low);

  const ends = LINE_SERIES.map((series) => {
    const last = rows[rows.length - 1]?.[series.key] ?? null;
    return { series, y: last === null ? null : y(last) };
  })
    .filter((end): end is { series: (typeof LINE_SERIES)[number]; y: number } => end.y !== null)
    .sort((a, b) => a.y - b.y);
  for (let index = 1; index < ends.length; index++) {
    if (ends[index].y - ends[index - 1].y < 15) ends[index].y = ends[index - 1].y + 15;
  }

  function onMove(event: React.PointerEvent<SVGRectElement>) {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const pointerX = event.clientX - box.left;
    let best = 0;
    rows.forEach((_, index) => {
      if (Math.abs(x(index) - pointerX) < Math.abs(x(best) - pointerX)) best = index;
    });
    const row = rows[best];
    const entries = LINE_SERIES.filter((series) => row[series.key] !== null).sort((a, b) => (row[a.key] as number) - (row[b.key] as number));
    setCursor(best);
    setTip({
      x: x(best),
      y: y(row.rps ?? high),
      title: `Matchday ${row.matchday} · lower is better`,
      rows: entries.map((series) => ({ color: series.color, label: series.label, value: score(row[series.key] as number) })),
    });
  }

  return (
    <div ref={ref} className="relative w-full">
      {width > 0 && (
        <svg
          viewBox={`0 0 ${width} ${height}`}
          height={height}
          role="img"
          aria-label="Average ranked probability score per matchday for the model, the closing market and the base rate"
          className="block w-full overflow-visible"
        >
          {axisTicks(low, high, 0.04).map((tick) => (
            <g key={tick}>
              <line x1={margin.left} x2={width - margin.right} y1={y(tick)} y2={y(tick)} stroke="var(--chart-grid)" />
              <text x={margin.left - 8} y={y(tick) + 4} textAnchor="end" className="chart-text">
                {tick.toFixed(2)}
              </text>
            </g>
          ))}
          <text x={0} y={10} className="chart-text">
            RPS ↓
          </text>
          {rows.map((row, index) => (
            <text key={row.matchday} x={x(index)} y={height - 10} textAnchor="middle" className="chart-text">
              MD {row.matchday}
            </text>
          ))}
          {cursor !== null && <line x1={x(cursor)} x2={x(cursor)} y1={margin.top} y2={height - margin.bottom} stroke="var(--chart-faint)" strokeDasharray="3 3" />}
          {LINE_SERIES.map((series) => {
            const points = rows.flatMap((row, index) => (row[series.key] === null ? [] : [{ x: x(index), y: y(row[series.key] as number) }]));
            return (
              <g key={series.key}>
                <polyline points={points.map((p) => `${p.x},${p.y}`).join(" ")} fill="none" stroke={series.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                {points.map((p, index) => (
                  <circle key={index} cx={p.x} cy={p.y} r={4} fill={series.color} stroke="var(--bp-surface-1)" strokeWidth={2} />
                ))}
              </g>
            );
          })}
          {(width >= 480 || single) &&
            ends.map((end) => (
              <text key={end.series.key} x={single ? x(0) + 14 : width - margin.right + 10} y={end.y + 4} className="chart-label">
                {single ? `${end.series.label} ${score(rows[0][end.series.key] as number)}` : end.series.label}
              </text>
            ))}
          <rect
            x={margin.left - 20}
            y={0}
            width={Math.max(0, width - margin.left - margin.right + 40)}
            height={height}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => {
              setTip(null);
              setCursor(null);
            }}
          />
        </svg>
      )}
      <Tip tip={tip} />
    </div>
  );
}

export function RpsLineTable({ rows }: { rows: MatchdayRow[] }) {
  return (
    <DataTable
      head={["Matchday", "Model", "Closing market", "Base rate", "Favourite won"]}
      rows={rows.map((row) => [
        row.matchday,
        row.rps === null ? "n/a" : score(row.rps),
        row.bookmaker_rps === null ? "n/a" : score(row.bookmaker_rps),
        row.base_rate_rps === null ? "n/a" : score(row.base_rate_rps),
        `${Math.round((row.hit_rate ?? 0) * row.n_resolved)} of ${row.n_resolved}`,
      ])}
    />
  );
}

export type DotRow = { key: string; label: string; value: number; kind: "model" | "market"; serving: boolean };

/** RPS by forecaster as a dot plot on a zoomed axis; the serving model is the filled dot. */
export function DotPlot({ rows }: { rows: DotRow[] }) {
  const { ref, width } = useWidth();
  const [tip, setTip] = useState<TipState>(null);
  const rowHeight = 40;
  const margin = { left: Math.min(170, width * 0.42), right: 56, top: 6, bottom: 30 };
  const height = margin.top + margin.bottom + rowHeight * rows.length;
  const values = rows.map((row) => row.value);
  const low = Math.floor((Math.min(...values) - 0.001) * 200) / 200;
  const high = Math.ceil((Math.max(...values) + 0.001) * 200) / 200;
  const x = (value: number) => margin.left + ((value - low) * (width - margin.left - margin.right)) / (high - low);

  return (
    <div ref={ref} className="relative w-full">
      {width > 0 && (
        <svg viewBox={`0 0 ${width} ${height}`} height={height} role="img" aria-label="Ranked probability score by forecaster, lower is better" className="block w-full overflow-visible">
          {axisTicks(low, high, 0.005).map((tick) => (
            <g key={tick}>
              <line x1={x(tick)} x2={x(tick)} y1={margin.top} y2={height - margin.bottom} stroke="var(--chart-grid)" />
              <text x={x(tick)} y={height - 10} textAnchor="middle" className="chart-text">
                {tick.toFixed(3)}
              </text>
            </g>
          ))}
          {rows.map((row, index) => {
            const cy = margin.top + rowHeight * index + rowHeight / 2;
            const color = row.kind === "model" ? COLORS.model : COLORS.market;
            return (
              <g key={row.key}>
                <text x={margin.left - 12} y={cy + 4} textAnchor="end" className="chart-label">
                  {row.label}
                </text>
                <line x1={margin.left} x2={x(row.value)} y1={cy} y2={cy} stroke="var(--bp-border)" strokeWidth={2} />
                <circle cx={x(row.value)} cy={cy} r={6} fill={row.serving ? color : "var(--bp-surface-1)"} stroke={color} strokeWidth={2} />
                <text x={x(row.value) + 12} y={cy + 4} className="chart-text">
                  {score(row.value)}
                </text>
                <rect
                  x={0}
                  y={cy - rowHeight / 2}
                  width={width}
                  height={rowHeight}
                  fill="transparent"
                  onPointerMove={() =>
                    setTip({
                      x: x(row.value),
                      y: cy,
                      title: row.serving ? "Serving model" : row.kind === "model" ? "Model variant" : "Bookmaker consensus",
                      rows: [{ color, label: row.label, value: score(row.value) }],
                    })
                  }
                  onPointerLeave={() => setTip(null)}
                />
              </g>
            );
          })}
        </svg>
      )}
      <Tip tip={tip} />
    </div>
  );
}

export function DotTable({ rows }: { rows: DotRow[] }) {
  return <DataTable head={["Forecaster", "RPS"]} rows={rows.map((row) => [row.serving ? `${row.label} (serving)` : row.label, score(row.value)])} />;
}

/** Predicted probability against how often it happened; points on the dashed diagonal are perfectly calibrated. */
export function ReliabilityChart({ bins }: { bins: CalibrationBin[] }) {
  const { ref, width } = useWidth();
  const [tip, setTip] = useState<TipState>(null);
  const side = Math.min(width, 360);
  const margin = { left: 40, right: 12, top: 10, bottom: 34 };
  const inner = side - margin.left - margin.right;
  const height = inner + margin.top + margin.bottom;
  const x = (value: number) => margin.left + value * inner;
  const y = (value: number) => margin.top + (1 - value) * inner;
  const ticks = [0, 0.2, 0.4, 0.6, 0.8, 1];

  return (
    <div ref={ref} className="relative w-full">
      {width > 0 && (
        <svg viewBox={`0 0 ${side} ${height}`} height={height} style={{ maxWidth: side }} role="img" aria-label="Predicted probability against how often it happened" className="block w-full overflow-visible">
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={x(tick)} x2={x(tick)} y1={y(0)} y2={y(1)} stroke="var(--chart-grid)" />
              <line x1={x(0)} x2={x(1)} y1={y(tick)} y2={y(tick)} stroke="var(--chart-grid)" />
              <text x={x(tick)} y={height - 16} textAnchor="middle" className="chart-text">
                {Math.round(tick * 100)}%
              </text>
              {tick > 0 && (
                <text x={margin.left - 6} y={y(tick) + 4} textAnchor="end" className="chart-text">
                  {Math.round(tick * 100)}%
                </text>
              )}
            </g>
          ))}
          <text x={x(0.5)} y={height - 2} textAnchor="middle" className="chart-text">
            predicted
          </text>
          <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--chart-faint)" strokeWidth={1.5} strokeDasharray="4 4" />
          <polyline points={bins.map((bin) => `${x(bin.predicted_mean)},${y(bin.observed_rate)}`).join(" ")} fill="none" stroke={COLORS.model} strokeWidth={2} strokeLinejoin="round" />
          {bins.map((bin) => (
            <g key={bin.lower}>
              <circle cx={x(bin.predicted_mean)} cy={y(bin.observed_rate)} r={4.5} fill={COLORS.model} stroke="var(--bp-surface-1)" strokeWidth={2} />
              <circle
                cx={x(bin.predicted_mean)}
                cy={y(bin.observed_rate)}
                r={14}
                fill="transparent"
                onPointerMove={() =>
                  setTip({
                    x: x(bin.predicted_mean),
                    y: y(bin.observed_rate),
                    title: `Predicted about ${Math.round(bin.predicted_mean * 100)}%`,
                    rows: [
                      { color: COLORS.model, label: "Happened", value: `${Math.round(bin.observed_rate * 100)}%` },
                      { color: "var(--chart-faint)", label: "Predictions", value: String(bin.count) },
                    ],
                  })
                }
                onPointerLeave={() => setTip(null)}
              />
            </g>
          ))}
        </svg>
      )}
      <Tip tip={tip} />
    </div>
  );
}

export function ReliabilityTable({ bins }: { bins: CalibrationBin[] }) {
  return (
    <DataTable
      head={["Predicted", "Happened", "Predictions"]}
      rows={bins.map((bin) => [`${Math.round(bin.predicted_mean * 100)}%`, `${Math.round(bin.observed_rate * 100)}%`, bin.count])}
    />
  );
}

export const LINE_LEGEND = [
  { label: "Model", color: COLORS.model },
  { label: "Closing market", color: COLORS.market },
  { label: "Base rate", color: COLORS.base },
];

export const DOT_LEGEND = [
  { label: "Model", color: COLORS.model },
  { label: "Market", color: COLORS.market },
];
