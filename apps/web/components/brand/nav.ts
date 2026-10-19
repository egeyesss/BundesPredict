export type NavPlan = "free" | "pro" | "demo";

export type NavUser = {
  name: string | null;
  email: string;
  plan: NavPlan;
  chatsUsed: number;
  chatsLimit: number;
};

export type NavLink = { href: string; label: string; hint?: string };

export const NAV_LINKS: readonly NavLink[] = [
  { href: "/matchday", label: "Matchday", hint: "this weekend's odds" },
  { href: "/chat", label: "Chat", hint: "ask the agent" },
  { href: "/track-record", label: "Track record", hint: "how it's doing" },
];

export const ACCOUNT_LINK: NavLink = { href: "/account", label: "Account", hint: "plan, email" };

export const PLAN_LABEL: Record<NavPlan, string> = { free: "Free", pro: "Pro", demo: "Demo" };

export function displayName(user: Pick<NavUser, "name" | "email" | "plan">): string {
  return user.name ?? (user.plan === "demo" ? "Demo visitor" : user.email.split("@")[0]);
}

export function quotaSummary(user: NavUser): string {
  if (user.plan === "pro") return "Pro · fair use";
  const left = Math.max(0, user.chatsLimit - user.chatsUsed);
  return user.plan === "demo"
    ? `${left} of ${user.chatsLimit} demo chats left`
    : `${left} of ${user.chatsLimit} free chats left today`;
}
