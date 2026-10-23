import { Check, TriangleAlert, X } from "lucide-react";

import { cn } from "@/lib/utils";

export type Status = "good" | "warning" | "critical";

const STYLE: Record<Status, { text: string; dot: string; Icon: typeof Check }> = {
  good: { text: "text-[#4ADE80]", dot: "bg-status-good text-bp-bg", Icon: Check },
  warning: { text: "text-[#FCD34D]", dot: "bg-status-warning text-bp-bg", Icon: TriangleAlert },
  critical: { text: "text-[#FCA5A5]", dot: "bg-status-critical text-white", Icon: X },
};

/** A status is never colour alone: the dot carries an icon and the text says what it means. */
export function StatusBadge({ status, children, className }: { status: Status; children: string; className?: string }) {
  const { text, dot, Icon } = STYLE[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono text-[11px] font-medium", text, className)}>
      <span aria-hidden="true" className={cn("grid size-3.5 place-items-center rounded-full", dot)}>
        <Icon className="size-2.5" strokeWidth={3} />
      </span>
      {children}
    </span>
  );
}
