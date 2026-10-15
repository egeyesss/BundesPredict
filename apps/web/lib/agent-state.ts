import { useCallback, useEffect, useMemo, useReducer } from "react";

import type { PredictStreamEvent, StageEvent } from "@/lib/api/types";

/** How long the orb holds its "done" flash before settling back to idle. */
export const DONE_HOLD_MS = 1200;

/**
 * The predict stream's frames as generated from the API schema, plus two events the
 * client adds: `send` when the user submits and `settle` when the done hold elapses.
 */
export type AgentEvent = PredictStreamEvent | { event: "send" } | { event: "settle" };

/** `seq` counts tool calls in the run so the orb can pulse again for a repeated tool. */
export type OrbState =
  | { phase: "idle" }
  | { phase: "thinking" }
  | { phase: "tool"; tool: string; seq: number }
  | { phase: "done" }
  | { phase: "error"; message: string };

export type StageStatus = "running" | "done" | "failed";

export type Stage = {
  name: string;
  status: StageStatus;
  /** The server's one-line description once the tool finished. */
  summary: string | null;
};

export type AgentState = {
  orb: OrbState;
  calls: number;
  stages: readonly Stage[];
};

export const INITIAL_AGENT_STATE: AgentState = { orb: { phase: "idle" }, calls: 0, stages: [] };

const TOOL_CAPTIONS: Record<string, string> = {
  predict_match: "Running the model",
  get_team_form: "Checking form",
  lookup_player: "Looking up the squad",
  get_weather: "Checking the weather",
  predict_match_with_context: "Applying adjustments",
  get_recent_results: "Checking the latest results",
  get_upcoming_fixtures: "Looking up the schedule",
};

const UNKNOWN_TOOL_CAPTION = "Working on it";

export function captionFor(state: OrbState): string {
  switch (state.phase) {
    case "idle":
      return "";
    case "thinking":
      return "Reading the question";
    case "tool":
      return TOOL_CAPTIONS[state.tool] ?? UNKNOWN_TOOL_CAPTION;
    case "done":
      return "Done";
    case "error":
      return state.message;
  }
}

/** The caption a finished or unfinished stage shows when the server sent no summary. */
export function stageLabel(stage: Stage): string {
  return stage.summary ?? TOOL_CAPTIONS[stage.name] ?? UNKNOWN_TOOL_CAPTION;
}

function settleStages(stages: readonly Stage[], to: StageStatus): readonly Stage[] {
  return stages.some((stage) => stage.status === "running")
    ? stages.map((stage) => (stage.status === "running" ? { ...stage, status: to } : stage))
    : stages;
}

function reduceStage(state: AgentState, data: StageEvent): AgentState {
  if (data.type === "tool_call") {
    const calls = state.calls + 1;
    return {
      orb: { phase: "tool", tool: data.name, seq: calls },
      calls,
      stages: [...state.stages, { name: data.name, status: "running", summary: null }],
    };
  }
  if (data.type !== "tool_result") return state;

  const index = state.stages.findLastIndex((stage) => stage.name === data.name && stage.status === "running");
  const stages =
    index === -1
      ? state.stages
      : state.stages.map((stage, position) =>
          position === index ? { ...stage, status: data.ok ? ("done" as const) : ("failed" as const), summary: data.summary } : stage,
        );
  const finishedCurrentTool = state.orb.phase === "tool" && state.orb.tool === data.name;
  return { ...state, orb: finishedCurrentTool ? { phase: "thinking" } : state.orb, stages };
}

export function reduceAgentState(state: AgentState, event: AgentEvent): AgentState {
  const { phase } = state.orb;

  switch (event.event) {
    case "send":
      return { orb: { phase: "thinking" }, calls: 0, stages: [] };
    case "error":
      return { ...state, orb: { phase: "error", message: event.data.message }, stages: settleStages(state.stages, "failed") };
    case "settle":
      return phase === "done" ? { ...state, orb: { phase: "idle" } } : state;
    case "result":
      return phase === "thinking" || phase === "tool"
        ? { ...state, orb: { phase: "done" }, stages: settleStages(state.stages, "done") }
        : state;
    case "stage":
      return phase === "thinking" || phase === "tool" ? reduceStage(state, event.data) : state;
    case "conversation":
    case "quota":
      return state;
  }
}

export function foldAgentState(events: readonly AgentEvent[]): AgentState {
  return events.reduce(reduceAgentState, INITIAL_AGENT_STATE);
}

export function foldAgentEvents(events: readonly AgentEvent[]): OrbState {
  return foldAgentState(events).orb;
}

export function stagesFromEvents(events: readonly AgentEvent[]): readonly Stage[] {
  return foldAgentState(events).stages;
}

/** Holds the agent state for one chat run; feed it the events as they arrive. */
export function useAgentState() {
  const [state, dispatch] = useReducer(reduceAgentState, INITIAL_AGENT_STATE);
  const { phase } = state.orb;

  useEffect(() => {
    if (phase !== "done") return;
    const timer = setTimeout(() => dispatch({ event: "settle" }), DONE_HOLD_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  const stableDispatch = useCallback((event: AgentEvent) => dispatch(event), []);

  return useMemo(
    () => ({ state: state.orb, stages: state.stages, caption: captionFor(state.orb), dispatch: stableDispatch }),
    [state, stableDispatch],
  );
}
