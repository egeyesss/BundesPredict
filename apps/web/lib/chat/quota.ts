import type { Me, Usage } from "@/lib/api/types";

type Plan = Me["plan"];

export function chatsLeft(usage: Usage): number {
  return Math.max(0, usage.limit - usage.used);
}

/** Pro is capped at 100 a day for fair use, but the interface never presents it as a limit. */
export function isExhausted(plan: Plan, usage: Usage): boolean {
  return plan !== "pro" && chatsLeft(usage) === 0;
}

export function meterText(plan: Plan, usage: Usage): string {
  if (plan === "pro") return "Pro · fair use";
  const left = chatsLeft(usage);
  return plan === "demo" ? `${left} of ${usage.limit} demo chats left` : `${left} of ${usage.limit} free chats left today`;
}

/** The daily reset is midnight UTC; people read it in their own clock. */
export function resetTimeText(resetsAt: string, { timeZone, locale }: { timeZone?: string; locale?: string } = {}): string {
  return new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", timeZone }).format(new Date(resetsAt));
}
