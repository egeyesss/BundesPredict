import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { recordedStreams, type RecordedStreamName } from "@/lib/api/mocks/streams";
import { KNOWN_TOOL_NAMES } from "@/lib/api/types";

import {
  DONE_HOLD_MS,
  INITIAL_AGENT_STATE,
  captionFor,
  foldAgentEvents,
  foldAgentState,
  reduceAgentState,
  stagesFromEvents,
  useAgentState,
  type AgentEvent,
} from "./agent-state";

const send: AgentEvent = { event: "send" };
const toolCall = (name: string): AgentEvent => ({ event: "stage", data: { type: "tool_call", name, input: {} } });
const recorded = (name: RecordedStreamName): AgentEvent[] => [{ event: "send" }, ...recordedStreams[name]];
const toolResult = (name: string, ok = true): AgentEvent => ({
  event: "stage",
  data: { type: "tool_result", name, ok, summary: `${name} finished` },
});
const result: AgentEvent = { event: "result", data: recordedStreams.happy.at(-1)!.data as never };
const failure = (message = "The model is unavailable right now."): AgentEvent => ({
  event: "error",
  data: { code: "model_unavailable", message },
});
const settle: AgentEvent = { event: "settle" };

const run = (...events: AgentEvent[]) => foldAgentEvents(events);

describe("transitions from the orb state diagram", () => {
  it("starts idle", () => {
    expect(INITIAL_AGENT_STATE.orb).toEqual({ phase: "idle" });
  });

  it("idle -> thinking on send", () => {
    expect(run(send)).toEqual({ phase: "thinking" });
  });

  it("thinking -> tool(name) on tool_call", () => {
    expect(run(send, toolCall("predict_match"))).toEqual({ phase: "tool", tool: "predict_match", seq: 1 });
  });

  it("tool -> thinking on the matching tool_result", () => {
    expect(run(send, toolCall("predict_match"), toolResult("predict_match"))).toEqual({ phase: "thinking" });
  });

  it("a failed tool_result still returns to thinking so the agent can retry", () => {
    expect(run(send, toolCall("lookup_player"), toolResult("lookup_player", false))).toEqual({ phase: "thinking" });
  });

  it("thinking -> done on result", () => {
    expect(run(send, result)).toEqual({ phase: "done" });
  });

  it("tool -> done on result when no tool_result arrived", () => {
    expect(run(send, toolCall("predict_match"), result)).toEqual({ phase: "done" });
  });

  it("done -> idle on settle", () => {
    expect(run(send, result, settle)).toEqual({ phase: "idle" });
  });

  it("any state -> error on error, carrying the message", () => {
    const message = "Quota check failed.";
    expect(run(failure(message))).toEqual({ phase: "error", message });
    expect(run(send, failure(message))).toEqual({ phase: "error", message });
    expect(run(send, toolCall("get_weather"), failure(message))).toEqual({ phase: "error", message });
    expect(run(send, result, failure(message))).toEqual({ phase: "error", message });
  });

  it("error -> thinking on the next send", () => {
    expect(run(send, failure(), send)).toEqual({ phase: "thinking" });
  });

  it("done -> thinking when the user sends again before the hold ends", () => {
    expect(run(send, result, send)).toEqual({ phase: "thinking" });
  });
});

describe("tool calls", () => {
  it("increments seq on every tool_call, even for the same tool, so the orb can pulse each time", () => {
    const first = run(send, toolCall("predict_match"));
    const second = run(send, toolCall("predict_match"), toolResult("predict_match"), toolCall("predict_match"));
    expect(first).toMatchObject({ seq: 1 });
    expect(second).toMatchObject({ phase: "tool", tool: "predict_match", seq: 2 });
  });

  it("keeps counting across tool_results within a run", () => {
    const state = run(send, toolCall("a"), toolResult("a"), toolCall("b"), toolResult("b"), toolCall("c"));
    expect(state).toEqual({ phase: "tool", tool: "c", seq: 3 });
  });

  it("restarts the count on a new send", () => {
    const state = run(send, toolCall("a"), result, settle, send, toolCall("b"));
    expect(state).toEqual({ phase: "tool", tool: "b", seq: 1 });
  });

  it("moves straight to the next tool when a call arrives before the previous result", () => {
    expect(run(send, toolCall("get_team_form"), toolCall("get_weather"))).toEqual({
      phase: "tool",
      tool: "get_weather",
      seq: 2,
    });
  });

  it("ignores a tool_result for a tool that is not the current one", () => {
    expect(run(send, toolCall("get_weather"), toolResult("get_team_form"))).toEqual({
      phase: "tool",
      tool: "get_weather",
      seq: 1,
    });
  });

  it("treats an unknown tool name as a tool state", () => {
    expect(run(send, toolCall("check_referee"))).toEqual({ phase: "tool", tool: "check_referee", seq: 1 });
    expect(run(send, toolCall("check_referee"), toolResult("check_referee"))).toEqual({ phase: "thinking" });
  });
});

describe("events that must not change the state", () => {
  it("ignores conversation and quota frames", () => {
    const conversation: AgentEvent = { event: "conversation", data: { id: "c", title: "t" } };
    const anonymousConversation: AgentEvent = { event: "conversation", data: { id: null, title: "t" } };
    const quota: AgentEvent = { event: "quota", data: { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" } };
    expect(run(send, conversation, anonymousConversation, quota)).toEqual({ phase: "thinking" });
    expect(run(conversation, quota)).toEqual({ phase: "idle" });
  });

  it("ignores a result when nothing was sent", () => {
    expect(run(result)).toEqual({ phase: "idle" });
  });

  it("ignores a late result after an error", () => {
    expect(run(send, failure("boom"), result)).toEqual({ phase: "error", message: "boom" });
  });

  it("ignores tool frames after an error", () => {
    expect(run(send, failure("boom"), toolCall("predict_match"))).toEqual({ phase: "error", message: "boom" });
  });

  it("ignores settle unless the state is done", () => {
    expect(run(send, settle)).toEqual({ phase: "thinking" });
    expect(run(send, failure("boom"), settle)).toEqual({ phase: "error", message: "boom" });
  });

  it("returns the same state object when nothing changes", () => {
    const before = reduceAgentState(INITIAL_AGENT_STATE, settle);
    expect(before).toBe(INITIAL_AGENT_STATE);
  });

  it("ignores a stage frame with an unrecognised type", () => {
    const odd = { event: "stage", data: { type: "heartbeat" } } as unknown as AgentEvent;
    expect(run(send, odd)).toEqual({ phase: "thinking" });
  });
});

describe("recorded streams", () => {
  const phasesOf = (name: RecordedStreamName) => {
    const phases: string[] = [];
    let state = INITIAL_AGENT_STATE;
    for (const event of recorded(name)) {
      state = reduceAgentState(state, event);
      phases.push(state.orb.phase);
    }
    return phases;
  };

  it("walks the tool-heavy stream through thinking, seven tools and done", () => {
    const phases = phasesOf("tool_heavy");
    expect(new Set(phases)).toEqual(new Set(["thinking", "tool", "done"]));
    expect(phases.filter((phase, index) => phase === "tool" && phases[index - 1] !== "tool")).toHaveLength(7);
    expect(phases.at(-1)).toBe("done");
  });

  it("pulses the orb once per call, including the repeated get_team_form", () => {
    const seqs: number[] = [];
    let state = INITIAL_AGENT_STATE;
    for (const event of recorded("tool_heavy")) {
      state = reduceAgentState(state, event);
      if (state.orb.phase === "tool") seqs.push(state.orb.seq);
    }
    expect(seqs).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("only uses tool names the contract lists", () => {
    const names = foldAgentState(recorded("tool_heavy")).stages.map((stage) => stage.name);
    for (const name of names) expect(KNOWN_TOOL_NAMES).toContain(name);
  });

  it.each(["happy", "last_chat", "tool_heavy"] as const)("%s ends in done with every stage finished", (name) => {
    const state = foldAgentState(recorded(name));
    expect(state.orb).toEqual({ phase: "done" });
    expect(state.stages.every((stage) => stage.status === "done")).toBe(true);
    expect(state.stages.every((stage) => stage.summary)).toBe(true);
  });

  it("keeps the server's summary on each stage", () => {
    const stages = foldAgentState(recorded("tool_heavy")).stages;
    expect(stages[0]).toEqual({
      name: "get_upcoming_fixtures",
      status: "done",
      summary: "2 fixtures, next Bayern Munich v 1.FSV Mainz 05",
    });
  });

  it("fails the stage whose tool errored, then ends in error with the server message", () => {
    const state = foldAgentState(recorded("error"));
    expect(state.stages).toEqual([{ name: "predict_match", status: "failed", summary: "No ratings for Real Madrid" }]);
    expect(state.orb).toEqual({ phase: "error", message: "The prediction could not be completed. Try again." });
  });

  it("recovers on a second send after the erroring stream", () => {
    const state = foldAgentState([...recorded("error"), ...recorded("happy")]);
    expect(state.orb).toEqual({ phase: "done" });
    expect(state.stages).toHaveLength(3);
  });
});

describe("captionFor", () => {
  it("is empty when idle", () => {
    expect(captionFor({ phase: "idle" })).toBe("");
  });

  it("names each phase", () => {
    expect(captionFor({ phase: "thinking" })).toBe("Reading the question");
    expect(captionFor({ phase: "done" })).toBe("Done");
    expect(captionFor({ phase: "error", message: "It broke." })).toBe("It broke.");
  });

  it.each([
    ["predict_match", "Running the model"],
    ["get_team_form", "Checking form"],
    ["lookup_player", "Looking up the squad"],
    ["get_weather", "Checking the weather"],
    ["predict_match_with_context", "Applying adjustments"],
    ["get_recent_results", "Checking the latest results"],
    ["get_upcoming_fixtures", "Looking up the schedule"],
  ])("maps %s to %s", (tool, caption) => {
    expect(captionFor({ phase: "tool", tool, seq: 1 })).toBe(caption);
  });

  it("has a caption for every tool the contract lists", () => {
    for (const tool of KNOWN_TOOL_NAMES) expect(captionFor({ phase: "tool", tool, seq: 1 })).not.toBe("Working on it");
  });

  it("falls back to a generic caption for unknown tools", () => {
    expect(captionFor({ phase: "tool", tool: "check_referee", seq: 1 })).toBe("Working on it");
  });
});

describe("stagesFromEvents", () => {
  it("pairs each call with its result, keeping order", () => {
    const stages = stagesFromEvents([
      send,
      toolCall("predict_match"),
      toolResult("predict_match"),
      toolCall("lookup_player"),
    ]);
    expect(stages).toEqual([
      { name: "predict_match", status: "done", summary: "predict_match finished" },
      { name: "lookup_player", status: "running", summary: null },
    ]);
  });

  it("marks a failed result", () => {
    const stages = stagesFromEvents([send, toolCall("lookup_player"), toolResult("lookup_player", false)]);
    expect(stages[0].status).toBe("failed");
  });

  it("starts over on a new send", () => {
    const stages = stagesFromEvents([send, toolCall("a"), toolResult("a"), result, send, toolCall("b")]);
    expect(stages.map((stage) => stage.name)).toEqual(["b"]);
  });

  it("pairs repeated calls to the same tool one by one", () => {
    const stages = stagesFromEvents([send, toolCall("a"), toolResult("a"), toolCall("a")]);
    expect(stages.map((stage) => stage.status)).toEqual(["done", "running"]);
  });
});

describe("useAgentState", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("drives the reducer through dispatch", () => {
    const { result: hook } = renderHook(() => useAgentState());
    act(() => hook.current.dispatch(send));
    expect(hook.current.state).toEqual({ phase: "thinking" });
    act(() => hook.current.dispatch(toolCall("get_weather")));
    expect(hook.current.state).toEqual({ phase: "tool", tool: "get_weather", seq: 1 });
  });

  it("settles from done to idle after the hold", () => {
    const { result: hook } = renderHook(() => useAgentState());
    act(() => {
      hook.current.dispatch(send);
      hook.current.dispatch(result);
    });
    expect(hook.current.state).toEqual({ phase: "done" });
    act(() => {
      vi.advanceTimersByTime(DONE_HOLD_MS - 1);
    });
    expect(hook.current.state).toEqual({ phase: "done" });
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(hook.current.state).toEqual({ phase: "idle" });
  });

  it("a send during the hold cancels the settle", () => {
    const { result: hook } = renderHook(() => useAgentState());
    act(() => {
      hook.current.dispatch(send);
      hook.current.dispatch(result);
    });
    act(() => hook.current.dispatch(send));
    act(() => {
      vi.advanceTimersByTime(DONE_HOLD_MS * 2);
    });
    expect(hook.current.state).toEqual({ phase: "thinking" });
  });

  it("exposes the caption and the stage list", () => {
    const { result: hook } = renderHook(() => useAgentState());
    act(() => {
      hook.current.dispatch(send);
      hook.current.dispatch(toolCall("predict_match"));
    });
    expect(hook.current.caption).toBe("Running the model");
    expect(hook.current.stages).toHaveLength(1);
  });
});
