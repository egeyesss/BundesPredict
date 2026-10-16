import type { AgentEvent } from "@/lib/agent-state";
import { recordedStreams, type RecordedStreamName } from "@/lib/api/mocks/streams";

/** An event and how long to wait after the previous one before it fires. */
export type TimedEvent = readonly [delayMs: number, event: AgentEvent];

const FIRST_TOOL_DELAY_MS = 700;
const PACE_MS = { conversation: 150, quota: 100, tool_call: 350, tool_result: 800, result: 500, error: 900 } as const;

/**
 * The recordings carry no timing, so replay paces them like a live run: a pause while the
 * agent reads the question, then roughly a second per tool.
 */
function paced(name: RecordedStreamName): readonly TimedEvent[] {
  const frames = recordedStreams[name];
  const timed = frames.map((frame, index): TimedEvent => {
    const afterQuota = frames[index - 1]?.event === "quota";
    const delay = frame.event === "stage" ? (afterQuota ? FIRST_TOOL_DELAY_MS : PACE_MS[frame.data.type]) : PACE_MS[frame.event];
    return [delay, frame];
  });
  return [[0, { event: "send" }], ...timed];
}

export const STREAMS = {
  toolHeavy: { label: "Tool-heavy: seven tool calls, then the answer", events: paced("tool_heavy") },
  withError: { label: "Stream that errors after a failed tool", events: paced("error") },
} as const;
