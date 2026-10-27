import { STEPS } from "./steps";

/**
 * `welcome` is the opening card, `tour` the numbered walk, `tip` one stop opened from a hotspot,
 * and `idle` everything else (hotspots show once the welcome card has been answered).
 */
export type TourPhase = "welcome" | "tour" | "tip" | "idle";

export type TourState = {
  phase: TourPhase;
  index: number;
  /** The welcome card has been dealt with, by starting the tour or by looking around. */
  answered: boolean;
  completed: boolean;
};

export type TourAction =
  | { type: "start" }
  | { type: "dismiss" }
  | { type: "next" }
  | { type: "back" }
  | { type: "skip" }
  | { type: "goto"; index: number }
  | { type: "tip"; index: number }
  | { type: "restart" }
  | { type: "resume"; index: number }
  | { type: "load"; state: TourState };

export const INITIAL_TOUR: TourState = { phase: "welcome", index: 0, answered: false, completed: false };

const LAST = STEPS.length - 1;
const clamp = (index: number) => Math.min(Math.max(index, 0), LAST);

export function tourReducer(state: TourState, action: TourAction): TourState {
  switch (action.type) {
    case "start":
      return { ...state, phase: "tour", index: 0, answered: true, completed: false };
    case "dismiss":
      return { ...state, phase: "idle", answered: true };
    case "next":
      if (state.phase === "tip") return { ...state, phase: "idle" };
      if (state.phase !== "tour") return state;
      return state.index >= LAST ? { ...state, phase: "idle", completed: true } : { ...state, index: state.index + 1 };
    case "back":
      return state.phase === "tour" ? { ...state, index: clamp(state.index - 1) } : state;
    case "skip":
      return state.phase === "welcome" || state.phase === "tour" || state.phase === "tip" ? { ...state, phase: "idle", answered: true } : state;
    case "goto":
      return state.phase === "tour" ? { ...state, index: clamp(action.index) } : state;
    case "tip":
      return { ...state, phase: "tip", index: clamp(action.index) };
    case "restart":
      return { ...INITIAL_TOUR };
    case "resume":
      return { ...state, phase: "tour", index: clamp(action.index), answered: true };
    case "load":
      return { ...action.state, index: clamp(action.state.index) };
  }
}
