import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { subscribeFrames } from "./frame-loop";

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("subscribeFrames", () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] }));
  afterEach(() => {
    setHidden(false);
    vi.useRealTimers();
  });

  it("calls every subscriber each frame with the elapsed time", () => {
    const first = vi.fn();
    const second = vi.fn();
    const stopFirst = subscribeFrames(first);
    const stopSecond = subscribeFrames(second);
    vi.advanceTimersByTime(48);
    expect(first.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(second.mock.calls.length).toBe(first.mock.calls.length);
    expect(first.mock.calls[1][1]).toBeGreaterThan(0);
    stopFirst();
    stopSecond();
  });

  it("caps a long gap between frames at 100ms", () => {
    const callback = vi.fn();
    const stop = subscribeFrames(callback);
    vi.advanceTimersByTime(16);
    callback.mockClear();
    vi.setSystemTime(Date.now() + 5000);
    vi.advanceTimersByTime(16);
    for (const [, delta] of callback.mock.calls) expect(delta).toBeLessThanOrEqual(100);
    stop();
  });

  it("stops scheduling frames once the last subscriber leaves", () => {
    const callback = vi.fn();
    const stop = subscribeFrames(callback);
    vi.advanceTimersByTime(32);
    stop();
    callback.mockClear();
    vi.advanceTimersByTime(200);
    expect(callback).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not run subscribers while the tab is hidden and resumes afterwards", () => {
    const callback = vi.fn();
    const stop = subscribeFrames(callback);
    vi.advanceTimersByTime(32);
    setHidden(true);
    callback.mockClear();
    vi.advanceTimersByTime(200);
    expect(callback).not.toHaveBeenCalled();
    setHidden(false);
    vi.advanceTimersByTime(48);
    expect(callback).toHaveBeenCalled();
    stop();
  });
});
