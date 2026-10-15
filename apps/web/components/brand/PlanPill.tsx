import { PLAN_LABEL, type NavPlan } from "./nav";
import { cn } from "@/lib/utils";

const PLAN_STYLES: Record<NavPlan, string> = {
  free: "border-border text-muted-foreground",
  pro: "border-transparent bg-linear-to-br from-bp-text to-odds-draw-lead text-bp-bg",
  demo: "border-status-warning/25 bg-status-warning/10 text-status-warning",
};

export function PlanPill({ plan, className }: { plan: NavPlan; className?: string }) {
  return (
    <span
      data-plan={plan}
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-1 font-mono text-[11px] leading-none font-semibold tracking-wider whitespace-nowrap uppercase",
        PLAN_STYLES[plan],
        className,
      )}
    >
      {PLAN_LABEL[plan]}
    </span>
  );
}
