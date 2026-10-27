import type { Me } from "@/lib/api/types";
import { chatsLeft, formatTimeOfDay, planState, quotaPlan } from "@/lib/account/plan";

import { Banner } from "@/components/states/Banner";

import { Card, Eyebrow } from "./AccountUi";

export function UsageCard({ me, timeZone }: { me: Me; timeZone: string | null }) {
  const state = planState(me);
  const { used, limit, resets_at } = me.usage;
  const resetsAt = formatTimeOfDay(resets_at, timeZone);
  const allowance = quotaPlan(me);

  if (allowance === "pro") {
    return (
      <Card aria-label="Usage">
        <Eyebrow>Usage</Eyebrow>
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-sm text-bp-text-muted">
            <strong className="font-display text-[34px] leading-none font-bold text-bp-text tabular-nums">{used}</strong>{" "}
            chat{used === 1 ? "" : "s"} today
          </p>
          <span className="text-xs text-bp-text-muted">fair use: {limit} a day</span>
        </div>
        <span className="text-xs text-bp-text-muted">Resets at {resetsAt}</span>
      </Card>
    );
  }

  const left = chatsLeft(me.usage);
  const noun = allowance === "demo" ? "demo chats" : "free chats";
  return (
    <Card aria-label="Usage">
      <Eyebrow>Usage</Eyebrow>
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm text-bp-text-muted">
          <strong className="font-display text-[34px] leading-none font-bold text-bp-text tabular-nums">{left}</strong> of {limit} {noun} left
        </p>
        <span className="text-xs text-bp-text-muted">{allowance === "demo" ? "for this demo" : `resets at ${resetsAt}`}</span>
      </div>
      <div className="flex gap-1" aria-hidden="true">
        {Array.from({ length: limit }, (_, index) => (
          <i key={index} className={index < used ? "h-1.5 flex-1 rounded-[3px] bg-bp-border" : "h-1.5 flex-1 rounded-[3px] bg-bp-text"} />
        ))}
      </div>
      {state === "free_exhausted" && (
        <Banner tone="warn" icon="!">
          You&apos;ve used today&apos;s free chats. Matchday odds stay open; chats come back at {resetsAt}.
        </Banner>
      )}
    </Card>
  );
}
