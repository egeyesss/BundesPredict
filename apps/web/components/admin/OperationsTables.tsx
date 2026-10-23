import { Card } from "@/components/account/AccountUi";
import { formatAgo, formatMoney } from "@/lib/admin/format";
import type { AdminMetrics } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { Cell, DataTable } from "./DataTable";
import { StatusBadge } from "./StatusBadge";

function Heading({ title, description }: { title: string; description: string }) {
  return (
    <div className="grid min-w-0 gap-1">
      <h3 className="font-display text-[19px] leading-[1.15] font-semibold tracking-[0.02em]">{title}</h3>
      <p className="text-[13px] text-bp-text-muted">{description}</p>
    </div>
  );
}

export function ModeTag({ livemode }: { livemode: boolean }) {
  return (
    <span className={cn("rounded-[4px] border px-1.5 py-px font-mono text-[10px] font-medium uppercase", livemode ? "border-[#3a3a42] text-bp-text" : "border-bp-border text-bp-text-muted")}>
      {livemode ? "live" : "test"}
    </span>
  );
}

export function WebhookCard({ events, now }: { events: AdminMetrics["webhook_events"]; now: number }) {
  return (
    <Card>
      <Heading title="Stripe webhooks" description="Newest first. Stripe redelivers a failed event on its own; a failure drops off this list once a retry goes through." />
      {events.length === 0 ? (
        <p className="py-4 text-sm text-bp-text-muted">No webhook events yet. They appear after the first checkout.</p>
      ) : (
        <DataTable label="Recent Stripe webhook events" head={["Event", "Mode", "Received", "Status"]}>
          {events.map((event) => (
            <tr key={event.event_id} className="group">
              <Cell>
                {event.type}
                {event.error && <span className="mt-0.5 block text-xs [overflow-wrap:anywhere] text-[#71717A]">{event.error}</span>}
              </Cell>
              <Cell>
                <ModeTag livemode={event.livemode} />
              </Cell>
              <Cell mono>{formatAgo(event.received_at, now)}</Cell>
              <Cell>{event.status === "failed" ? <StatusBadge status="critical">failed</StatusBadge> : <StatusBadge status="good">processed</StatusBadge>}</Cell>
            </tr>
          ))}
        </DataTable>
      )}
    </Card>
  );
}

export function FailedPaymentsCard({ payments, now }: { payments: AdminMetrics["failed_payments"]; now: number }) {
  return (
    <Card>
      <Heading title="Failed payments" description="Pro stays on until the paid period ends." />
      {payments.length === 0 ? (
        <div className="py-4">
          <StatusBadge status="good">no failed payments</StatusBadge>
        </div>
      ) : (
        <DataTable label="Subscribers with a failed payment" head={["Subscriber", "Mode", "Amount", "Failed"]}>
          {payments.map((payment) => (
            <tr key={`${payment.email}-${payment.failed_at}`} className="group">
              <Cell className="[overflow-wrap:anywhere]">{payment.email}</Cell>
              <Cell>
                <ModeTag livemode={payment.livemode} />
              </Cell>
              <Cell>{formatMoney(payment.amount_cents)}</Cell>
              <Cell mono>{formatAgo(payment.failed_at, now)}</Cell>
            </tr>
          ))}
        </DataTable>
      )}
    </Card>
  );
}
