import type { Me, Usage } from "@/lib/api/types";
import { meterText } from "@/lib/chat/quota";
import { cn } from "@/lib/utils";

/** How many chats are left: a pip per chat for capped plans, plain text for pro. */
export function QuotaMeter({ plan, usage }: { plan: Me["plan"]; usage: Usage }) {
  return (
    <div className="flex items-center gap-2 font-mono text-xs text-bp-text-muted">
      {plan !== "pro" && (
        <span aria-hidden="true" className="flex gap-[3px]">
          {Array.from({ length: usage.limit }, (_, index) => {
            const used = index < usage.used;
            return <i key={index} data-pip="" data-used={used} className={cn("h-1 w-3.5 rounded-sm", used ? "bg-bp-border" : "bg-bp-text")} />;
          })}
        </span>
      )}
      <span>{meterText(plan, usage)}</span>
    </div>
  );
}
