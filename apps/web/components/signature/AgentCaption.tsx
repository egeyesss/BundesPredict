import { captionFor, type OrbState } from "@/lib/agent-state";
import { cn } from "@/lib/utils";

/**
 * What the agent is doing, in words. A polite live region, so screen readers hear
 * each step; the final explanation lives elsewhere and is not announced from here.
 */
export function AgentCaption({ state, className }: { state: OrbState; className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      data-state={state.phase}
      className={cn(
        "min-h-[1.5em] font-mono text-xs text-bp-text data-[state=done]:text-bp-text-muted data-[state=error]:text-bp-red-text data-[state=idle]:text-bp-text-muted",
        className,
      )}
    >
      {captionFor(state)}
    </div>
  );
}
