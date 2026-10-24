import type { AgentEvent } from "@/lib/agent-state";
import type { PredictStreamEvent } from "@/lib/api/types";

export type ReplayStep = { delayMs: number; event: AgentEvent };
export type ReplayResult = Extract<PredictStreamEvent, { event: "result" }>["data"];

const THINK_MS = 800;
const TOOL_RUN_MS = 850;
const BETWEEN_TOOLS_MS = 300;
const ANSWER_MS = 400;

/**
 * Turns a recorded predict stream into timed agent events. `conversation` and `quota` frames only
 * matter to the chat page, so they are dropped; `instant` is the reduced-motion schedule.
 */
export function replaySchedule(stream: readonly PredictStreamEvent[], { instant }: { instant: boolean }): ReplayStep[] {
  const steps: ReplayStep[] = [{ delayMs: 0, event: { event: "send" } }];
  let previous: PredictStreamEvent | null = null;

  for (const frame of stream) {
    if (frame.event === "conversation" || frame.event === "quota") continue;
    const delayMs = instant ? 0 : delayBefore(frame, previous);
    steps.push({ delayMs, event: frame });
    previous = frame;
  }
  return steps;
}

function delayBefore(frame: PredictStreamEvent, previous: PredictStreamEvent | null): number {
  if (frame.event === "result") return ANSWER_MS;
  if (frame.event !== "stage") return 0;
  if (frame.data.type === "tool_result") return TOOL_RUN_MS;
  return previous === null ? THINK_MS : BETWEEN_TOOLS_MS;
}

export function replayResult(stream: readonly PredictStreamEvent[]): ReplayResult | null {
  const frame = stream.find((candidate) => candidate.event === "result");
  return frame?.event === "result" ? frame.data : null;
}

/** The score grids are 121 numbers each and the landing page never draws them, so they stay out of the client bundle. */
export function compactDemoStream(stream: readonly PredictStreamEvent[]): PredictStreamEvent[] {
  return stream
    .filter((frame) => frame.event !== "conversation" && frame.event !== "quota")
    .map((frame) =>
      frame.event === "result"
        ? {
            ...frame,
            data: {
              ...frame.data,
              baseline: frame.data.baseline && { ...frame.data.baseline, score_grid: [] },
              adjusted: frame.data.adjusted && { ...frame.data.adjusted, score_grid: [] },
            },
          }
        : frame,
    );
}
