import { afterEach, describe, expect, it, vi } from "vitest";

import { clearTour, loadTour, saveTour } from "./tour-storage";

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("tour storage", () => {
  it("round-trips the state for one demo user and keeps users apart", () => {
    saveTour(7, { phase: "tour", index: 4, answered: true, completed: false });
    expect(loadTour(7)).toEqual({ phase: "tour", index: 4, answered: true, completed: false });
    expect(loadTour(8)).toBeNull();
  });

  it("never persists a hotspot tip, which reopens as idle", () => {
    saveTour(7, { phase: "tip", index: 4, answered: true, completed: true });
    expect(loadTour(7)).toEqual({ phase: "idle", index: 4, answered: true, completed: true });
  });

  it("ignores values that are not a tour state", () => {
    window.sessionStorage.setItem("bp-tour:7", '{"phase":"nope","index":"x"}');
    expect(loadTour(7)).toBeNull();
    window.sessionStorage.setItem("bp-tour:7", "not json");
    expect(loadTour(7)).toBeNull();
  });

  it("survives storage that throws on read and write", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(loadTour(7)).toBeNull();
    expect(() => saveTour(7, { phase: "idle", index: 0, answered: true, completed: false })).not.toThrow();
    expect(() => clearTour(7)).not.toThrow();
  });

  it("remembers that a checkout is under way so the tour can offer to resume", async () => {
    const { markCheckoutStarted, takeCheckoutResume } = await import("./tour-storage");
    expect(takeCheckoutResume(7)).toBe(false);
    markCheckoutStarted(7);
    expect(takeCheckoutResume(7)).toBe(true);
    expect(takeCheckoutResume(7)).toBe(false);
  });
});
