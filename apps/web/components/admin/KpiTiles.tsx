import { Info } from "lucide-react";

import { costStatus, formatMoney, formatPercent } from "@/lib/admin/format";
import type { AdminMetrics } from "@/lib/api/types";

import { StatusBadge, type Status } from "./StatusBadge";

const COST_BADGE = {
  healthy: { status: "good", label: "healthy" },
  watch: { status: "warning", label: "watch" },
  high: { status: "critical", label: "high" },
} as const satisfies Record<string, { status: Status; label: string }>;

function Tile({ label, value, children }: { label: string; value: string; children?: React.ReactNode }) {
  return (
    <div className="grid min-w-0 content-start gap-1 rounded-xl border border-bp-border bg-bp-surface-1 px-4 py-3.5">
      <span className="text-[13px] text-bp-text-muted">{label}</span>
      <strong className="font-display text-[34px] leading-none font-bold tabular-nums">{value}</strong>
      <span className="flex flex-wrap items-center gap-x-1.5 font-mono text-[11px] text-[#71717A]">{children}</span>
    </div>
  );
}

export function KpiTiles({ metrics }: { metrics: AdminMetrics }) {
  const chats = metrics.chats_per_day.reduce((sum, day) => sum + day.pro + day.free + day.demo, 0);
  const ratio = metrics.cost_to_revenue_per_pro_user;
  const status = costStatus(ratio);
  const badge = status && COST_BADGE[status];
  const noLiveSubscribers = metrics.active_subscribers === 0;

  return (
    <section aria-label="Key numbers" className="grid grid-cols-2 gap-2.5 min-[561px]:grid-cols-3 min-[1081px]:grid-cols-6">
      <Tile label="Pro subscribers" value={String(metrics.active_subscribers)}>
        live mode
      </Tile>
      <Tile label="MRR" value={formatMoney(metrics.mrr_cents)}>
        live mode only
      </Tile>
      <Tile label="New sign-ups" value={String(metrics.signups_7d)}>
        last 7 days · {metrics.signups_30d} in 30
      </Tile>
      <Tile label="Churn" value={formatPercent(metrics.monthly_churn)}>
        {noLiveSubscribers ? "no live subscribers yet" : "lost in 30 days"}
      </Tile>
      <Tile label="Chats" value={chats.toLocaleString("en-CA")}>
        last {metrics.chats_per_day.length} days
      </Tile>
      <Tile label="Agent cost" value={formatMoney(metrics.llm_cost_per_user_cents)}>
        {ratio === null || !badge ? (
          "per user, 30 days"
        ) : (
          <>
            {Math.round(ratio * 100)}% of Pro revenue <StatusBadge status={badge.status}>{badge.label}</StatusBadge>
          </>
        )}
      </Tile>
    </section>
  );
}

export function EmptyLiveNote() {
  return (
    <div role="note" className="grid grid-cols-[34px_minmax(0,1fr)] items-start gap-3 rounded-[14px] border border-bp-border bg-bp-surface-1 p-5">
      <span aria-hidden="true" className="grid size-[34px] place-items-center rounded-full border border-bp-border bg-bp-surface-2">
        <Info className="size-4" />
      </span>
      <div className="grid gap-1">
        <h2 className="font-display text-[22px] leading-tight font-semibold tracking-[0.02em]">No paying subscribers yet</h2>
        <p className="max-w-[60ch] text-sm text-bp-text-muted">
          MRR, churn and cost per Pro user fill in after the first live-mode subscription. Test-mode checkouts never count in the tiles above; their numbers sit in the test-mode card below.
        </p>
      </div>
    </div>
  );
}
