import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { StateTone } from "./StateMessage";

const BANNER_TONE: Record<StateTone, { box: string; icon: string }> = {
  info: { box: "border-bp-border bg-bp-surface-1 text-bp-text", icon: "bg-bp-text text-bp-bg" },
  warn: { box: "border-status-warning/25 bg-[#1A1405] text-[#FDE68A]", icon: "bg-status-warning text-[#1A1405]" },
  crit: { box: "border-status-critical/30 bg-[#1C0D0E] text-[#FECACA]", icon: "bg-status-critical text-white" },
};

type BannerProps = {
  tone?: StateTone;
  icon: ReactNode;
  role?: "alert" | "status";
  children: ReactNode;
  className?: string;
};

export function Banner({ tone = "info", icon, role = "status", children, className }: BannerProps) {
  const styles = BANNER_TONE[tone];
  return (
    <div
      role={role}
      className={cn("grid grid-cols-[22px_minmax(0,1fr)] items-center gap-2.5 rounded-[var(--bp-radius)] border px-3 py-2.5 text-[13px]", styles.box, className)}
    >
      <span aria-hidden="true" className={cn("grid size-[22px] place-items-center rounded-full text-[11px] font-bold", styles.icon)}>
        {icon}
      </span>
      <span>{children}</span>
    </div>
  );
}
