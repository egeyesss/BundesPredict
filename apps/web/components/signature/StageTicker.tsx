import { stageLabel, type Stage, type StageStatus } from "@/lib/agent-state";
import { cn } from "@/lib/utils";

const MARK: Record<StageStatus, string> = { running: "›", done: "✓", failed: "!" };
const SPOKEN: Record<StageStatus, string> = { running: "in progress", done: "completed", failed: "failed" };

export type StageTickerProps = {
  stages: readonly Stage[];
  /** Fold the list to its summary line, for example once the explanation starts typing. */
  collapsed?: boolean;
  className?: string;
};

/** A compact list of what the agent has done so far, one line per tool call. */
export function StageTicker({ stages, collapsed = false, className }: StageTickerProps) {
  if (stages.length === 0) return null;

  return (
    <details open={!collapsed} className={cn("group", className)}>
      <summary className="inline-flex cursor-pointer list-none gap-1.5 rounded-sm font-mono text-xs text-bp-text-muted before:text-bp-text-muted before:content-['\25B8'] group-open:before:content-['\25BE'] [&::-webkit-details-marker]:hidden">
        {stages.length} agent {stages.length === 1 ? "step" : "steps"}
      </summary>
      <ul className="mt-2 grid list-none gap-1 p-0 font-mono text-xs text-bp-text-muted">
        {stages.map((stage, index) => (
          <li key={index} data-status={stage.status} className="grid grid-cols-[1.2ch_minmax(0,1fr)] gap-2">
            <span aria-hidden="true" className={stage.status === "done" ? "text-bp-text" : "text-bp-red-text"}>
              {MARK[stage.status]}
            </span>
            <span>
              {stageLabel(stage)} <span>{stage.name}</span>
              <span className="sr-only">{SPOKEN[stage.status]}</span>
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
