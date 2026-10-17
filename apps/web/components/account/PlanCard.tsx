"use client";

import { Banner } from "@/components/states/Banner";
import { Button } from "@/components/ui/button";
import { formatDay, planState, type PlanState } from "@/lib/account/plan";
import type { Me } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { Card, Eyebrow } from "./AccountUi";
import { useBillingRedirect } from "./useBillingRedirect";

const FREE_PERKS = ["Probabilities for every fixture", "3 agent chats a day", "Saved chat history"];
const PRO_PERKS = ["Unlimited chats (fair use, 100 a day)", "Saved chat history", "Everything in Free"];

function Perks({ items }: { items: readonly string[] }) {
  return (
    <ul className="grid gap-2 text-sm text-[#D4D4D8]">
      {items.map((item) => (
        <li key={item} className="grid grid-cols-[16px_minmax(0,1fr)] gap-2.5 before:text-bp-text-muted before:content-['✓']">
          {item}
        </li>
      ))}
    </ul>
  );
}

function PlanHeader({ name, aside }: { name: string; aside: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="grid gap-1">
        <Eyebrow>Your plan</Eyebrow>
        <h2 className="font-display text-[40px] leading-none font-bold">{name}</h2>
      </div>
      <span className="text-sm font-medium text-bp-text-muted">{aside}</span>
    </div>
  );
}

export function PlanCard({ me, timeZone }: { me: Me; timeZone: string | null }) {
  const state: PlanState = planState(me);
  const billing = useBillingRedirect();
  const periodEnd = me.subscription ? formatDay(me.subscription.current_period_end, timeZone) : null;
  const busy = billing.pending !== null;
  const isPro = state === "pro" || state === "cancelling" || state === "past_due";

  return (
    <Card
      id="billing"
      aria-label="Plan"
      className={cn(isPro && "border-[#3a3a42] bg-[radial-gradient(120%_120%_at_100%_0%,rgb(244_244_245/0.06),transparent_60%)]")}
    >
      {(state === "free" || state === "free_exhausted") && (
        <>
          <PlanHeader name="Free" aside="$0" />
          <Perks items={FREE_PERKS} />
          <Banner icon="↑">
            <b>Pro is $5/month.</b> Unlimited chats (fair use). Cancel any time.
          </Banner>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" disabled={busy} onClick={() => void billing.start("checkout")}>
              {billing.pending === "checkout" ? "Opening Stripe…" : "Upgrade to Pro"}
            </Button>
          </div>
        </>
      )}

      {state === "pro" && (
        <>
          <PlanHeader name="Pro" aside="$5 / month" />
          <p className="text-sm text-bp-text-muted">
            Renews on <b className="text-bp-text">{periodEnd}</b>.
          </p>
          <Perks items={PRO_PERKS} />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="lg" disabled={busy} onClick={() => void billing.start("portal")}>
              {billing.pending === "portal" ? "Opening Stripe…" : "Manage billing"}
            </Button>
            <span className="text-xs text-bp-text-muted">Opens Stripe&apos;s billing portal: card, invoices, cancel.</span>
          </div>
        </>
      )}

      {state === "cancelling" && (
        <>
          <PlanHeader name="Pro" aside={`until ${periodEnd}`} />
          <Banner icon="i">
            You cancelled. Pro stays on until <b>{periodEnd}</b>, then you&apos;re back on Free. Nothing else is charged.
          </Banner>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" disabled={busy} onClick={() => void billing.start("portal")}>
              Keep Pro
            </Button>
            <Button variant="ghost" size="lg" disabled={busy} onClick={() => void billing.start("portal")}>
              Manage billing
            </Button>
          </div>
        </>
      )}

      {state === "past_due" && (
        <>
          <PlanHeader name="Pro" aside="$5 / month" />
          <Banner tone="warn" role="alert" icon="!">
            <b>Your last payment didn&apos;t go through.</b> Pro stays on until {periodEnd}. Update your card before then to keep it.
          </Banner>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" disabled={busy} onClick={() => void billing.start("portal")}>
              Update card
            </Button>
          </div>
        </>
      )}

      {state === "demo" && (
        <>
          <PlanHeader name="Demo" aside="test mode" />
          <p className="text-sm text-bp-text-muted">A temporary account for trying everything. It&apos;s deleted after 24 hours.</p>
          <Banner icon="i">
            Upgrading here opens Stripe&apos;s test checkout. Use card <b className="tabular-nums">4242 4242 4242 4242</b>, any future date, any CVC.
          </Banner>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" disabled={busy} onClick={() => void billing.start("checkout")}>
              Try the upgrade
            </Button>
          </div>
        </>
      )}

      {billing.error && (
        <Banner tone="crit" role="alert" icon="!">
          {billing.error}
        </Banner>
      )}
    </Card>
  );
}
