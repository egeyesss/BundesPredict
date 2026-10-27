import { describe, expect, it } from "vitest";

import { STEPS } from "./steps";
import { INITIAL_TOUR, tourReducer, type TourState } from "./tour-state";

const last = STEPS.length - 1;
const at = (index: number): TourState => ({ phase: "tour", index, answered: true, completed: false });

describe("tourReducer", () => {
  it("opens on the welcome card for a visitor who has not answered it", () => {
    expect(INITIAL_TOUR).toEqual({ phase: "welcome", index: 0, answered: false, completed: false });
  });

  it("starts the tour at the first stop", () => {
    expect(tourReducer(INITIAL_TOUR, { type: "start" })).toMatchObject({ phase: "tour", index: 0, answered: true });
  });

  it("looking around first closes the card and keeps the hotspots on", () => {
    expect(tourReducer(INITIAL_TOUR, { type: "dismiss" })).toMatchObject({ phase: "idle", answered: true, completed: false });
  });

  it("walks the stops in order and stops at the ends", () => {
    let state = tourReducer(INITIAL_TOUR, { type: "start" });
    const seen = [state.index];
    for (let step = 0; step < STEPS.length + 3; step++) {
      state = tourReducer(state, { type: "next" });
      if (state.phase !== "tour") break;
      seen.push(state.index);
    }
    expect(seen).toEqual(STEPS.map((_, index) => index));
    expect(tourReducer(at(0), { type: "back" }).index).toBe(0);
    expect(tourReducer(at(4), { type: "back" }).index).toBe(3);
  });

  it("finishing from the last stop marks the tour completed", () => {
    expect(tourReducer(at(last), { type: "next" })).toMatchObject({ phase: "idle", completed: true });
  });

  it("skipping leaves the tour unfinished but answered", () => {
    expect(tourReducer(at(6), { type: "skip" })).toMatchObject({ phase: "idle", answered: true, completed: false });
  });

  it("a single hotspot tip opens one stop and closes back to idle without touching progress", () => {
    const idle: TourState = { phase: "idle", index: 3, answered: true, completed: true };
    const tip = tourReducer(idle, { type: "tip", index: 9 });
    expect(tip).toMatchObject({ phase: "tip", index: 9 });
    expect(tourReducer(tip, { type: "next" })).toMatchObject({ phase: "idle", completed: true });
    expect(tourReducer(tip, { type: "back" })).toBe(tip);
    expect(tourReducer(tip, { type: "skip" })).toMatchObject({ phase: "idle", completed: true });
  });

  it("restart returns to the welcome card", () => {
    expect(tourReducer({ phase: "idle", index: 12, answered: true, completed: true }, { type: "restart" })).toMatchObject({
      phase: "welcome",
      index: 0,
      completed: false,
    });
  });

  it("jumps to a stop, clamped to the list", () => {
    expect(tourReducer(at(0), { type: "goto", index: 99 }).index).toBe(last);
    expect(tourReducer(at(5), { type: "goto", index: -4 }).index).toBe(0);
  });

  it("resuming after Checkout continues at the stop after the upgrade", () => {
    const idle: TourState = { phase: "idle", index: 9, answered: true, completed: false };
    expect(tourReducer(idle, { type: "resume", index: 10 })).toMatchObject({ phase: "tour", index: 10 });
  });

  it("loads a saved state, clamping a stale index", () => {
    expect(tourReducer(INITIAL_TOUR, { type: "load", state: { phase: "tour", index: 40, answered: true, completed: false } })).toEqual({
      phase: "tour",
      index: last,
      answered: true,
      completed: false,
    });
  });
});
