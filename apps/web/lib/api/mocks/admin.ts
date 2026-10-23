import type { AdminMetrics } from "../types";

const MS_PER_DAY = 86_400_000;
const NOW = Date.parse("2026-10-22T12:00:00Z");

const isoDay = (daysAgo: number) => new Date(NOW - daysAgo * MS_PER_DAY).toISOString().slice(0, 10);
const isoAgo = (minutes: number) => new Date(NOW - minutes * 60_000).toISOString();

/** 90 days of deterministic chat counts with a weekend bump, newest last. */
const chatsPerDay: AdminMetrics["chats_per_day"] = Array.from({ length: 90 }, (_, index) => {
  const daysAgo = 89 - index;
  const weekday = new Date(NOW - daysAgo * MS_PER_DAY).getUTCDay();
  const weekend = weekday === 0 || weekday === 5 || weekday === 6 ? 1.9 : 1;
  const growth = 0.35 + 0.65 * (index / 89);
  const wave = (offset: number) => 1 + ((index * 7 + offset) % 5) / 10;
  return {
    day: isoDay(daysAgo),
    pro: Math.round(22 * growth * weekend * wave(1)),
    free: Math.round(38 * growth * weekend * wave(3)),
    demo: Math.round(6 * (weekend > 1 ? 1.3 : 1) * wave(2)),
  };
});

export const adminMetrics: AdminMetrics = {
  generated_at: new Date(NOW).toISOString(),
  masked: false,
  active_subscribers: 0,
  mrr_cents: 0,
  test_mode: { active_subscribers: 6, mrr_cents: 3000 },
  signups_7d: 9,
  signups_30d: 31,
  monthly_churn: 0,
  chats_per_day: chatsPerDay,
  llm_cost_per_user_cents: 14.2,
  cost_to_revenue_per_pro_user: 0.28,
  pro_user_costs: [
    { email: "eren.k@example.com", cost_cents: 612 },
    { email: "sofia.m@example.org", cost_cents: 431 },
    { email: "jonas.w@example.com", cost_cents: 387 },
    { email: "mina.t@example.org", cost_cents: 302 },
    { email: "omar.h@example.com", cost_cents: 264 },
    { email: "lea.b@example.org", cost_cents: 86 },
  ],
  webhook_failures: [
    {
      event_id: "evt_1QmockFailed01",
      type: "customer.subscription.updated",
      livemode: false,
      error: "RuntimeError: stripe timed out",
      received_at: isoAgo(180),
    },
  ],
  webhook_events: [
    { event_id: "evt_1QmockOk0004", type: "invoice.paid", livemode: false, status: "processed", error: "", received_at: isoAgo(2) },
    { event_id: "evt_1QmockOk0003", type: "customer.subscription.updated", livemode: false, status: "processed", error: "", received_at: isoAgo(3) },
    { event_id: "evt_1QmockOk0002", type: "checkout.session.completed", livemode: false, status: "processed", error: "", received_at: isoAgo(9) },
    {
      event_id: "evt_1QmockFailed01",
      type: "customer.subscription.updated",
      livemode: false,
      status: "failed",
      error: "RuntimeError: stripe timed out",
      received_at: isoAgo(180),
    },
    { event_id: "evt_1QmockOk0001", type: "invoice.paid", livemode: false, status: "processed", error: "", received_at: isoAgo(1440) },
  ],
  failed_payments: [{ email: "a.keller@example.com", livemode: false, amount_cents: 500, failed_at: isoAgo(2880) }],
};

const maskEmail = (email: string) => `${email.slice(0, 1)}•••@${email.split("@")[1]}`;

export function maskedMetrics(metrics: AdminMetrics): AdminMetrics {
  return {
    ...metrics,
    masked: true,
    pro_user_costs: metrics.pro_user_costs.map((row) => ({ ...row, email: maskEmail(row.email) })),
    failed_payments: metrics.failed_payments.map((row) => ({ ...row, email: maskEmail(row.email) })),
  };
}

export const ADMIN_RANGES = [7, 30, 90] as const;

export function adminMetricsFor(days: number, masked: boolean): AdminMetrics {
  const base = { ...adminMetrics, chats_per_day: adminMetrics.chats_per_day.slice(-days) };
  return masked ? maskedMetrics(base) : base;
}
