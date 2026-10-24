"use client";

import { useState } from "react";

import { axisScale, labelEvery } from "@/lib/admin/format";
import type { AdminMetrics } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { DataTable, Cell } from "./DataTable";
import { useWidth } from "./useWidth";

type Day = AdminMetrics["chats_per_day"][number];

const SERIES = [
  { key: "pro", label: "Pro", color: "var(--plan-pro)" },
  { key: "free", label: "Free", color: "var(--plan-free)" },
  { key: "demo", label: "Demo", color: "var(--plan-demo)" },
] as const;

const HEIGHT = 240;
const MARGIN = { left: 34, right: 6, top: 8, bottom: 26 };

const dayLabel = (iso: string, weekday: boolean) =>
  new Intl.DateTimeFormat("en-CA", weekday ? { weekday: "short", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T12:00:00Z`));

const total = (day: Day) => day.pro + day.free + day.demo;

export function ChatsChart({ days }: { days: Day[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<number | null>(null);

  const { top, ticks } = axisScale(Math.max(0, ...days.map(total)), 40);
  const plotWidth = width - MARGIN.left - MARGIN.right;
  const slot = plotWidth / days.length;
  const gap = Math.min(4, slot * 0.3);
  const y = (value: number) => MARGIN.top + (HEIGHT - MARGIN.top - MARGIN.bottom) * (1 - value / top);
  const step = labelEvery(days.length);
  const active = hovered === null ? null : days[hovered];

  const legend = (
    <ul className="flex flex-wrap gap-x-3.5 gap-y-1.5 text-[13px] text-bp-text-muted">
      {SERIES.map(({ key, label, color }) => (
        <li key={key} className="inline-flex items-center gap-1.5">
          <i aria-hidden="true" className="size-2.5 rounded-[2px]" style={{ background: color }} />
          {label}
        </li>
      ))}
    </ul>
  );

  const table = (
    <DataTable label="Chats per day by plan" head={["Day", "Pro", "Free", "Demo"]}>
      {days.map((day) => (
        <tr key={day.day} className="group">
          <Cell>{dayLabel(day.day, false)}</Cell>
          <Cell>{day.pro}</Cell>
          <Cell>{day.free}</Cell>
          <Cell>{day.demo}</Cell>
        </tr>
      ))}
    </DataTable>
  );

  return (
    <ChartFrame title="Chats per day, by plan" description="Plan is each user's plan today. Demo chats are capped per visitor." legend={legend} table={table}>
      <div ref={ref} className="relative" onPointerLeave={() => setHovered(null)}>
        <svg viewBox={`0 0 ${width} ${HEIGHT}`} height={HEIGHT} role="img" aria-label={`Chats per day by plan over the last ${days.length} days; the table view has every number`} className="block w-full overflow-visible">
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="#222227" />
              <text x={MARGIN.left - 6} y={y(tick) + 4} textAnchor="end" className="fill-bp-text-muted font-mono text-[11px]">
                {tick}
              </text>
            </g>
          ))}
          {days.map((day, index) => {
            const x = MARGIN.left + index * slot + gap / 2;
            const barWidth = Math.max(1, slot - gap);
            let accumulated = 0;
            const present = SERIES.filter(({ key }) => day[key] > 0);
            return (
              <g key={day.day} opacity={hovered === null || hovered === index ? 1 : 0.55}>
                {present.map(({ key, color }, position) => {
                  const value = day[key];
                  const lower = y(accumulated);
                  const upper = y(accumulated + value);
                  const height = Math.max(0, lower - upper - (accumulated > 0 ? 2 : 0));
                  accumulated += value;
                  const isTop = position === present.length - 1;
                  return <rect key={key} x={x} y={upper} width={barWidth} height={height} rx={isTop ? Math.min(3, barWidth / 2) : 0} fill={color} />;
                })}
                {(days.length - 1 - index) % step === 0 && (
                  <text x={x + barWidth / 2} y={HEIGHT - 8} textAnchor="middle" className="fill-bp-text-muted font-mono text-[11px]">
                    {dayLabel(day.day, days.length <= 7)}
                  </text>
                )}
                <rect
                  x={MARGIN.left + index * slot}
                  y={0}
                  width={slot}
                  height={HEIGHT}
                  fill="transparent"
                  onPointerMove={() => setHovered(index)}
                  onPointerEnter={() => setHovered(index)}
                />
              </g>
            );
          })}
        </svg>
        {active && hovered !== null && (
          <div
            role="status"
            className="pointer-events-none absolute z-10 min-w-[150px] rounded-lg border border-bp-border bg-bp-surface-2 px-2.5 py-2 text-xs shadow-[0_8px_24px_rgb(0_0_0/0.5)]"
            style={{ left: Math.min(Math.max(0, MARGIN.left + hovered * slot + 12), Math.max(0, width - 170)), top: Math.max(0, y(total(active)) - 78) }}
          >
            <div className="mb-1 font-mono text-[11px] text-bp-text-muted">
              {dayLabel(active.day, false)} · {total(active)} chats
            </div>
            {SERIES.map(({ key, label, color }) => (
              <div key={key} className="grid grid-cols-[10px_1fr_auto] items-center gap-2">
                <i aria-hidden="true" className="size-2 rounded-[2px]" style={{ background: color }} />
                <span>{label}</span>
                <b className="font-mono font-medium">{active[key]}</b>
              </div>
            ))}
          </div>
        )}
      </div>
    </ChartFrame>
  );
}
