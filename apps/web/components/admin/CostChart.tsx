"use client";

import { useState } from "react";

import { formatMoney } from "@/lib/admin/format";
import type { AdminMetrics } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { Cell, DataTable } from "./DataTable";
import { StatusBadge } from "./StatusBadge";
import { useWidth } from "./useWidth";

type ProUserCost = AdminMetrics["pro_user_costs"][number];

export const NET_REVENUE_CENTS = 455;

const ROW_HEIGHT = 30;
const MARGIN = { top: 22, bottom: 24, right: 90 };

const AXIS_STEP_CENTS = 200;

export function CostChart({ users }: { users: ProUserCost[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<number | null>(null);
  const labelWidth = Math.min(180, Math.max(110, width * 0.3));
  const height = MARGIN.top + MARGIN.bottom + users.length * ROW_HEIGHT;
  const maxCents = Math.max(NET_REVENUE_CENTS, ...users.map((user) => user.cost_cents));
  const axisMax = Math.ceil(maxCents / AXIS_STEP_CENTS) * AXIS_STEP_CENTS;
  const x = (cents: number) => labelWidth + ((width - labelWidth - MARGIN.right) * cents) / axisMax;
  const gridValues = Array.from({ length: axisMax / AXIS_STEP_CENTS + 1 }, (_, index) => index * AXIS_STEP_CENTS);

  const table = (
    <DataTable label="Agent cost per Pro user" head={["Pro user", "Agent cost", "Status"]}>
      {users.map((user) => (
        <tr key={user.email} className="group">
          <Cell>{user.email}</Cell>
          <Cell>{formatMoney(user.cost_cents)}</Cell>
          <Cell>
            {user.cost_cents > NET_REVENUE_CENTS ? (
              <StatusBadge status="critical">over the line</StatusBadge>
            ) : (
              <StatusBadge status="good">fine</StatusBadge>
            )}
          </Cell>
        </tr>
      ))}
    </DataTable>
  );

  return (
    <ChartFrame
      title="What each Pro subscriber costs to run"
      description={`Agent spend over the last 30 days for the ten heaviest Pro users, against the ${formatMoney(NET_REVENUE_CENTS)} each pays after Stripe's fee. Anyone past the line costs more than they bring in.`}
      table={table}
    >
      {users.length === 0 ? (
        <p className="py-6 text-sm text-bp-text-muted">No Pro user has asked the agent anything in the last 30 days.</p>
      ) : (
        <div ref={ref} className="relative" onPointerLeave={() => setHovered(null)}>
          <svg viewBox={`0 0 ${width} ${height}`} height={height} role="img" aria-label="Agent cost per Pro user against net revenue; the table view has every number" className="block w-full overflow-visible">
            {gridValues.map((cents) => (
              <g key={cents}>
                <line x1={x(cents)} x2={x(cents)} y1={MARGIN.top} y2={height - MARGIN.bottom} stroke="#222227" />
                <text x={x(cents)} y={height - 6} textAnchor="middle" className="fill-[#71717A] font-mono text-[11px]">
                  {formatMoney(cents)}
                </text>
              </g>
            ))}
            {users.map((user, index) => {
              const centerY = MARGIN.top + index * ROW_HEIGHT + ROW_HEIGHT / 2;
              const over = user.cost_cents > NET_REVENUE_CENTS;
              return (
                <g key={user.email} opacity={hovered === null || hovered === index ? 1 : 0.55}>
                  <text x={labelWidth - 10} y={centerY + 4} textAnchor="end" className="fill-bp-text-muted text-xs">
                    {user.email.length > 22 ? `${user.email.slice(0, 21)}…` : user.email}
                  </text>
                  <rect x={labelWidth} y={centerY - 7} width={Math.max(2, x(user.cost_cents) - labelWidth)} height={14} rx={3} fill={over ? "var(--status-critical)" : "var(--plan-pro)"} />
                  <text x={x(user.cost_cents) + 8} y={centerY + 4} className="fill-bp-text font-mono text-xs [paint-order:stroke] stroke-bp-surface-1 stroke-[5px]">
                    {formatMoney(user.cost_cents)}
                    {over ? "  ▲ over" : ""}
                  </text>
                  <rect x={0} y={centerY - ROW_HEIGHT / 2} width={width} height={ROW_HEIGHT} fill="transparent" onPointerEnter={() => setHovered(index)} onPointerMove={() => setHovered(index)} />
                </g>
              );
            })}
            <line x1={x(NET_REVENUE_CENTS)} x2={x(NET_REVENUE_CENTS)} y1={MARGIN.top - 8} y2={height - MARGIN.bottom} stroke="var(--bp-text)" strokeWidth={1.5} strokeDasharray="4 3" />
            <text x={x(NET_REVENUE_CENTS) + 6} y={MARGIN.top - 8} className="fill-bp-text font-mono text-xs">
              {formatMoney(NET_REVENUE_CENTS)} net revenue
            </text>
          </svg>
          {hovered !== null && (
            <div
              role="status"
              className="pointer-events-none absolute z-10 min-w-[150px] rounded-lg border border-bp-border bg-bp-surface-2 px-2.5 py-2 text-xs shadow-[0_8px_24px_rgb(0_0_0/0.5)]"
              style={{ left: Math.min(Math.max(0, x(users[hovered].cost_cents) + 12), Math.max(0, width - 190)), top: Math.max(0, MARGIN.top + hovered * ROW_HEIGHT - 52) }}
            >
              <div className="mb-1 font-mono text-[11px] text-bp-text-muted">{users[hovered].email}</div>
              <div className="grid grid-cols-[1fr_auto] gap-x-3">
                <span>Agent cost, 30 days</span>
                <b className="font-mono font-medium">{formatMoney(users[hovered].cost_cents)}</b>
                <span>Pays after fees</span>
                <b className="font-mono font-medium">{formatMoney(NET_REVENUE_CENTS)}</b>
              </div>
            </div>
          )}
        </div>
      )}
    </ChartFrame>
  );
}
