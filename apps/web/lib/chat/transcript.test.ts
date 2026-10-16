import { describe, expect, it } from "vitest";

import { recordedStreams } from "@/lib/api/mocks/streams";
import { sampleConversation } from "@/lib/api/mocks/data";
import type { AgentEvent } from "@/lib/agent-state";

import { INITIAL_TRANSCRIPT, isBusy, latestResult, transcriptReducer, type AssistantTurn, type Transcript, type TranscriptAction } from "./transcript";

function run(...actions: TranscriptAction[]): Transcript {
  return actions.reduce(transcriptReducer, INITIAL_TRANSCRIPT);
}

const agent = (event: AgentEvent): TranscriptAction => ({ type: "agent", event });
const send = (text = "Guirassy is out"): TranscriptAction => ({ type: "send", id: "t1", text });
const lastAssistant = (transcript: Transcript) => transcript.findLast((turn) => turn.kind === "assistant") as AssistantTurn;

describe("loading a saved conversation", () => {
  it("turns messages into finished turns that do not animate", () => {
    const transcript = run({ type: "load", messages: sampleConversation.messages });
    expect(transcript.map((turn) => turn.kind)).toEqual(["user", "assistant"]);
    const assistant = lastAssistant(transcript);
    expect(assistant).toMatchObject({ phase: "done", animate: false });
    expect(assistant.result?.adjustments).toHaveLength(1);
    expect(isBusy(transcript)).toBe(false);
  });
});

describe("sending", () => {
  it("adds the question and a working answer with the orb thinking", () => {
    const transcript = run(send());
    expect(transcript).toHaveLength(2);
    expect(transcript[0]).toMatchObject({ kind: "user", text: "Guirassy is out" });
    expect(lastAssistant(transcript)).toMatchObject({ phase: "working", agent: { orb: { phase: "thinking" } } });
    expect(isBusy(transcript)).toBe(true);
  });

  it("folds the recorded stream into stages, then holds the result for typing", () => {
    const events = recordedStreams.happy as AgentEvent[];
    const transcript = run(send(), ...events.map(agent));
    const assistant = lastAssistant(transcript);
    expect(assistant.agent.stages).toHaveLength(3);
    expect(assistant).toMatchObject({ phase: "writing", animate: true, text: assistant.result?.explanation });
    expect(assistant.agent.orb.phase).toBe("done");
    expect(isBusy(transcript)).toBe(true);
  });

  it("is done once the explanation has been written", () => {
    const events = recordedStreams.happy as AgentEvent[];
    const transcript = run(send(), ...events.map(agent), { type: "written" });
    expect(lastAssistant(transcript).phase).toBe("done");
    expect(isBusy(transcript)).toBe(false);
  });

  it("settles the orb back to idle after the done flash", () => {
    const events = recordedStreams.happy as AgentEvent[];
    const transcript = run(send(), ...events.map(agent), agent({ event: "settle" }));
    expect(lastAssistant(transcript).agent.orb.phase).toBe("idle");
  });

  it("ends in a failed turn with the server's message when the stream errors", () => {
    const events = recordedStreams.error as AgentEvent[];
    const transcript = run(send(), ...events.map(agent));
    expect(lastAssistant(transcript)).toMatchObject({
      phase: "failed",
      error: "The prediction could not be completed. Try again.",
    });
    expect(isBusy(transcript)).toBe(false);
  });

  it("marks a stream that stopped without a result as cut off", () => {
    const events = (recordedStreams.happy as AgentEvent[]).slice(0, 5);
    const transcript = run(send(), ...events.map(agent), { type: "cut", message: "The answer was cut off by a lost connection." });
    expect(lastAssistant(transcript)).toMatchObject({ phase: "cut_off", error: "The answer was cut off by a lost connection." });
    expect(lastAssistant(transcript).agent.stages.every((stage) => stage.status !== "running")).toBe(true);
  });

  it("keeps the question and remembers it for a retry when the server rejects before streaming", () => {
    const transcript = run(send("Kane is out"), { type: "reject", message: "The model isn't available right now. This chat wasn't counted." });
    expect(transcript).toHaveLength(2);
    expect(lastAssistant(transcript)).toMatchObject({
      phase: "failed",
      error: "The model isn't available right now. This chat wasn't counted.",
      retryText: "Kane is out",
    });
  });

  it("drops both turns when the question never reached the agent", () => {
    expect(run(send(), { type: "discard" })).toEqual([]);
  });
});

describe("latestResult", () => {
  it("is the newest assistant prediction, or null", () => {
    expect(latestResult(INITIAL_TRANSCRIPT)).toBeNull();
    expect(latestResult(run({ type: "load", messages: sampleConversation.messages }))?.prediction_id).toBe(1842);
  });
});
