import { INITIAL_AGENT_STATE, reduceAgentState, type AgentEvent, type AgentState } from "@/lib/agent-state";
import type { Message, PredictResponse } from "@/lib/api/types";

export type UserTurn = { kind: "user"; id: string; text: string };

/**
 * `working` while the agent runs, `writing` while the explanation types out, `done` once the
 * result card is on screen. `failed` and `cut_off` are the two ways a run can end without one.
 */
export type AssistantPhase = "working" | "writing" | "done" | "failed" | "cut_off";

export type AssistantTurn = {
  kind: "assistant";
  id: string;
  phase: AssistantPhase;
  agent: AgentState;
  text: string;
  result: PredictResponse | null;
  error: string | null;
  /** The question to resend when the failure left the chat uncounted. */
  retryText: string | null;
  /** Type the explanation out instead of showing it at once. */
  animate: boolean;
};

export type Turn = UserTurn | AssistantTurn;
export type Transcript = readonly Turn[];

export const INITIAL_TRANSCRIPT: Transcript = [];

export type TranscriptAction =
  | { type: "load"; messages: readonly Message[] }
  | { type: "send"; id: string; text: string }
  | { type: "agent"; event: AgentEvent }
  | { type: "written" }
  | { type: "cut"; message: string }
  | { type: "reject"; message: string }
  | { type: "discard" };

function workingAssistant(id: string, retryText: string): AssistantTurn {
  return {
    kind: "assistant",
    id: `${id}-answer`,
    phase: "working",
    agent: reduceAgentState(INITIAL_AGENT_STATE, { event: "send" }),
    text: "",
    result: null,
    error: null,
    retryText,
    animate: true,
  };
}

function updateLastAssistant(transcript: Transcript, update: (turn: AssistantTurn) => AssistantTurn): Transcript {
  const index = transcript.findLastIndex((turn) => turn.kind === "assistant");
  if (index === -1) return transcript;
  return transcript.map((turn, position) => (position === index ? update(turn as AssistantTurn) : turn));
}

function applyAgentEvent(turn: AssistantTurn, event: AgentEvent): AssistantTurn {
  const agent = reduceAgentState(turn.agent, event);
  if (event.event === "result" && turn.phase === "working") {
    return { ...turn, agent, phase: "writing", result: event.data, text: event.data.explanation };
  }
  if (event.event === "error" && turn.phase === "working") {
    return { ...turn, agent, phase: "failed", error: event.data.message };
  }
  return agent === turn.agent ? turn : { ...turn, agent };
}

export function transcriptReducer(transcript: Transcript, action: TranscriptAction): Transcript {
  switch (action.type) {
    case "load":
      return action.messages.map((message): Turn =>
        message.role === "user"
          ? { kind: "user", id: `message-${message.id}`, text: message.content }
          : {
              kind: "assistant",
              id: `message-${message.id}`,
              phase: "done",
              agent: INITIAL_AGENT_STATE,
              text: message.content,
              result: message.prediction,
              error: null,
              retryText: null,
              animate: false,
            },
      );
    case "send":
      return [...transcript, { kind: "user", id: action.id, text: action.text }, workingAssistant(action.id, action.text)];
    case "agent":
      return updateLastAssistant(transcript, (turn) => applyAgentEvent(turn, action.event));
    case "written":
      return updateLastAssistant(transcript, (turn) => (turn.phase === "writing" ? { ...turn, phase: "done" } : turn));
    case "cut":
      return updateLastAssistant(transcript, (turn) => {
        if (turn.phase !== "working") return turn;
        const agent = reduceAgentState(turn.agent, { event: "error", data: { code: "connection_lost", message: action.message } });
        return { ...turn, agent, phase: "cut_off", error: action.message };
      });
    case "reject":
      return updateLastAssistant(transcript, (turn) => {
        const agent = reduceAgentState(turn.agent, { event: "error", data: { code: "rejected", message: action.message } });
        return { ...turn, agent, phase: "failed", error: action.message };
      });
    case "discard":
      return transcript.slice(0, -2);
  }
}

export function isBusy(transcript: Transcript): boolean {
  const last = transcript.findLast((turn) => turn.kind === "assistant");
  return last !== undefined && (last.phase === "working" || last.phase === "writing");
}

export function latestResult(transcript: Transcript): PredictResponse | null {
  for (let index = transcript.length - 1; index >= 0; index--) {
    const turn = transcript[index];
    if (turn.kind === "assistant" && turn.result) return turn.result;
  }
  return null;
}
