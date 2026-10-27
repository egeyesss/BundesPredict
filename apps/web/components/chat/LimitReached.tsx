import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { Me, Usage } from "@/lib/api/types";
import { resetTimeText } from "@/lib/chat/quota";

type LimitReachedProps = {
  plan: Me["plan"];
  usage: Usage;
  timeZone?: string;
  locale?: string;
};

/** Replaces the composer once the plan's chats are spent, with the way forward for that plan. */
export function LimitReached({ plan, usage, timeZone, locale }: LimitReachedProps) {
  const demo = plan === "demo";
  return (
    <div role="status" data-tour="quota" className="grid gap-2.5 rounded-[var(--bp-radius)] border border-bp-border bg-bp-surface-1 px-4 py-3.5">
      <p className="m-0 text-sm text-bp-text-muted">
        <strong className="font-semibold text-bp-text">
          {demo ? `You've used all ${usage.limit} demo chats.` : `You've used today's ${usage.limit} free chats.`}
        </strong>{" "}
        {demo
          ? "Create a free account to keep going. Matchday odds stay open to everyone."
          : `They reset at ${resetTimeText(usage.resets_at, { timeZone, locale })} your time. Matchday odds stay open to everyone.`}
      </p>
      <div className="flex flex-wrap gap-2">
        {demo ? (
          <Button asChild>
            <Link href="/login">Start free</Link>
          </Button>
        ) : (
          <Button asChild>
            <Link href="/account">Upgrade to Pro · $5/month</Link>
          </Button>
        )}
        <Button asChild variant="secondary">
          <Link href="/matchday">Back to matchday</Link>
        </Button>
      </div>
    </div>
  );
}
