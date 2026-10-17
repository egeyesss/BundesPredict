import type { NavUser } from "@/components/brand/nav";
import type { Me, Usage } from "@/lib/api/types";

export type PlanState = "free" | "free_exhausted" | "pro" | "cancelling" | "past_due" | "demo";

export function planState(me: Me): PlanState {
  if (me.plan === "demo") return "demo";
  if (me.plan === "pro") {
    if (me.subscription?.cancel_at_period_end) return "cancelling";
    if (me.subscription?.status === "past_due") return "past_due";
    return "pro";
  }
  return chatsLeft(me.usage) === 0 ? "free_exhausted" : "free";
}

export function chatsLeft(usage: Usage): number {
  return Math.max(0, usage.limit - usage.used);
}

export function navUserFromMe(me: Me): NavUser {
  return {
    name: me.name,
    email: me.email,
    plan: me.plan,
    chatsUsed: me.usage.used,
    chatsLimit: me.usage.limit,
  };
}

// ICU puts a narrow no-break space before AM/PM, which breaks plain-text matching and copy-paste.
const plainSpaces = (text: string) => text.replace(/ /g, " ");

export function formatDay(iso: string, timeZone: string | null): string {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: timeZone ?? undefined }).format(new Date(iso));
}

export function formatTimeOfDay(iso: string, timeZone: string | null): string {
  return plainSpaces(
    new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: timeZone ?? undefined }).format(new Date(iso)),
  );
}
