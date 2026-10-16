import type { ElementType, ReactNode } from "react";

import { cn } from "@/lib/utils";

export type StateTone = "info" | "crit" | "warn";

const ICON_TONE: Record<StateTone, string> = {
  info: "border-bp-border bg-bp-surface-2 text-bp-text",
  crit: "border-status-critical/40 bg-status-critical/15 text-[#FCA5A5]",
  warn: "border-status-warning/30 bg-status-warning/10 text-[#FCD34D]",
};

type StateMessageProps = {
  tone?: StateTone;
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  as?: ElementType;
  className?: string;
};

/** An empty or error state: an icon, what happened and what to do about it, then the way out. */
export function StateMessage({ tone = "info", icon, title, children, actions, as: Heading = "h2", className }: StateMessageProps) {
  return (
    <div className={cn("grid justify-items-start gap-2.5", className)}>
      <span aria-hidden="true" className={cn("grid size-[34px] place-items-center rounded-full border", ICON_TONE[tone])}>
        {icon}
      </span>
      <Heading className="font-display text-[22px] leading-tight font-semibold tracking-[0.02em]">{title}</Heading>
      {children && <p className="max-w-[60ch] text-sm text-bp-text-muted">{children}</p>}
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
