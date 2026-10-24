import { Card } from "@/components/account/AccountUi";
import { formatMoney } from "@/lib/admin/format";
import type { AdminMetrics } from "@/lib/api/types";

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-[13px] text-bp-text-muted">{label}</dt>
      <dd className="font-display text-[34px] leading-none font-bold tabular-nums">{value}</dd>
    </div>
  );
}

export function RevenueCards({ metrics }: { metrics: AdminMetrics }) {
  return (
    <div className="grid gap-3.5">
      <Card>
        <div className="grid gap-1">
          <h3 className="font-display text-[19px] leading-[1.15] font-semibold tracking-[0.02em]">Monthly recurring revenue</h3>
          <p className="text-[13px] text-bp-text-muted">Live-mode subscriptions only, at 5.00 a month each.</p>
        </div>
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          <Figure label="MRR" value={formatMoney(metrics.mrr_cents)} />
          <Figure label="Paying subscribers" value={String(metrics.active_subscribers)} />
        </dl>
      </Card>
      <Card aria-labelledby="test-mode-heading">
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 id="test-mode-heading" className="font-display text-[19px] leading-[1.15] font-semibold tracking-[0.02em]">
              Test-mode subscriptions
            </h3>
            <span className="rounded-[4px] border border-status-warning/40 px-1.5 py-px font-mono text-[10px] font-medium text-[#FCD34D] uppercase">Test mode</span>
          </div>
          <p className="text-[13px] text-bp-text-muted">Stripe sandbox checkouts, including every demo account. They are never added to the live numbers above.</p>
        </div>
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          <Figure label="Test MRR" value={formatMoney(metrics.test_mode.mrr_cents)} />
          <Figure label="Test subscribers" value={String(metrics.test_mode.active_subscribers)} />
        </dl>
      </Card>
    </div>
  );
}
