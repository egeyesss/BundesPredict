import type { AgentEvent } from "@/lib/agent-state";

/** An event and how long to wait after the previous one before it fires. */
export type TimedEvent = readonly [delayMs: number, event: AgentEvent];

const QUOTA = { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" };
const RESULT = { explanation: "Sample explanation." };

export const STREAMS: Record<string, { label: string; events: readonly TimedEvent[] }> = {
  toolHeavy: {
    label: "Tool-heavy: four tools, then the answer",
    events: [
      [0, { event: "send" }],
      [150, { event: "conversation", data: { id: "c-1", title: "Kane is out" } }],
      [100, { event: "quota", data: QUOTA }],
      [700, { event: "stage", data: { type: "tool_call", name: "predict_match", input: { home: "Bayern", away: "Leipzig" } } }],
      [900, { event: "stage", data: { type: "tool_result", name: "predict_match", ok: true, summary: "Ran the model for Bayern v Leipzig" } }],
      [350, { event: "stage", data: { type: "tool_call", name: "lookup_player", input: { name: "Harry Kane" } } }],
      [900, { event: "stage", data: { type: "tool_result", name: "lookup_player", ok: true, summary: "Found Harry Kane: Bayern, striker" } }],
      [350, { event: "stage", data: { type: "tool_call", name: "get_weather", input: { team: "Bayern" } } }],
      [800, { event: "stage", data: { type: "tool_result", name: "get_weather", ok: true, summary: "Heavy rain forecast in Munich at kickoff" } }],
      [350, { event: "stage", data: { type: "tool_call", name: "predict_with_adjustments", input: {} } }],
      [1000, { event: "stage", data: { type: "tool_result", name: "predict_with_adjustments", ok: true, summary: "Applied 2 adjustments" } }],
      [500, { event: "result", data: RESULT }],
    ],
  },
  withError: {
    label: "Stream that errors after two tools",
    events: [
      [0, { event: "send" }],
      [150, { event: "conversation", data: { id: "c-2", title: "Form check" } }],
      [100, { event: "quota", data: QUOTA }],
      [700, { event: "stage", data: { type: "tool_call", name: "get_team_form", input: { team: "Dortmund" } } }],
      [900, { event: "stage", data: { type: "tool_result", name: "get_team_form", ok: true, summary: "Dortmund: 3 wins in the last 5" } }],
      [350, { event: "stage", data: { type: "tool_call", name: "predict_match", input: { home: "Dortmund", away: "Union" } } }],
      [900, { event: "error", data: { code: "model_unavailable", message: "The model is unavailable right now. Your chat was not counted." } }],
    ],
  },
};
