import { Eyebrow } from "@/components/account/AccountUi";
import { Banner } from "@/components/states/Banner";
import type { Range } from "@/lib/admin/load";
import type { AdminMetrics } from "@/lib/api/types";

import { ChatsChart } from "./ChatsChart";
import { CostChart } from "./CostChart";
import { EmptyLiveNote, KpiTiles } from "./KpiTiles";
import { FailedPaymentsCard, WebhookCard } from "./OperationsTables";
import { RangeFilter } from "./RangeFilter";
import { RevenueCards } from "./RevenueCards";

export function AdminDashboard({ metrics, range }: { metrics: AdminMetrics; range: Range }) {
  const now = Date.parse(metrics.generated_at);
  return (
    <div className="mx-auto grid w-full max-w-[1200px] gap-[18px] px-4 pt-8 pb-16">
      {metrics.masked && (
        <Banner tone="warn" icon="!">
          <b>Read-only demo view.</b>{" "}
          You&apos;re seeing the real dashboard. Emails are masked and nothing here can be changed.
        </Banner>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-5 gap-y-3">
        <div className="grid gap-1.5">
          <Eyebrow>Ops</Eyebrow>
          <h1 className="font-display text-[clamp(36px,5vw,52px)] leading-none font-bold">Dashboard</h1>
          <p className="text-bp-text-muted">Subscriptions, usage and what the agent costs to run.</p>
        </div>
        <RangeFilter selected={range} />
      </div>
      <KpiTiles metrics={metrics} />
      {metrics.active_subscribers === 0 && <EmptyLiveNote />}
      <div className="grid items-start gap-3.5 min-[900px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <ChatsChart days={metrics.chats_per_day} />
        <RevenueCards metrics={metrics} />
      </div>
      <CostChart users={metrics.pro_user_costs} />
      <div className="grid items-start gap-3.5 min-[900px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <WebhookCard events={metrics.webhook_events} now={now} />
        <FailedPaymentsCard payments={metrics.failed_payments} now={now} />
      </div>
    </div>
  );
}
