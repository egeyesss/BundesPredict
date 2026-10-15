import Link from "next/link";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { displayName, type NavUser } from "./nav";

export function AccountMenu({ user }: { user: NavUser }) {
  const name = displayName(user);
  const isFree = user.plan === "free";
  const billingLabel = isFree ? "Upgrade to Pro" : "Manage billing";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label="Account menu" data-focus-key="account" className="rounded-full">
          <Avatar className="size-9">
            <AvatarFallback className="bg-bp-surface-2 text-[13px] font-semibold text-bp-text">
              {name.charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={12} className="w-60">
        <div className="mb-1 grid gap-0.5 border-b border-border px-2.5 pt-2.5 pb-2">
          <span className="text-sm font-semibold text-bp-text">{name}</span>
          <span className="truncate text-xs text-bp-text-muted">{user.email}</span>
        </div>
        <DropdownMenuItem asChild>
          <Link href="/account" className="justify-between">
            Account <small className="font-mono text-[11px] text-bp-text-muted">plan, usage</small>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/account#billing" className="justify-between">
            {billingLabel}{" "}
            <small className="font-mono text-[11px] text-bp-text-muted">{isFree ? "$5/mo" : "Stripe"}</small>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/chat" className="justify-between">
            Chat history
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <a href="/logout">Sign out</a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
