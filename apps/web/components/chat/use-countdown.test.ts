import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCountdown } from "./use-countdown";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useCountdown", () => {
  it("is idle until started", () => {
    const { result } = renderHook(() => useCountdown());
    expect(result.current.secondsLeft).toBe(0);
    expect(result.current.active).toBe(false);
  });

  it("counts down once a second to zero and stops", () => {
    const { result } = renderHook(() => useCountdown());
    act(() => result.current.start(3));
    expect(result.current).toMatchObject({ secondsLeft: 3, active: true });
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.secondsLeft).toBe(2);
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current).toMatchObject({ secondsLeft: 0, active: false });
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.secondsLeft).toBe(0);
  });

  it("restarts from the new value", () => {
    const { result } = renderHook(() => useCountdown());
    act(() => result.current.start(5));
    act(() => vi.advanceTimersByTime(2000));
    act(() => result.current.start(10));
    expect(result.current.secondsLeft).toBe(10);
  });

  it("reports whether the countdown has finished, so the banner can say Ready", () => {
    const { result } = renderHook(() => useCountdown());
    expect(result.current.finished).toBe(false);
    act(() => result.current.start(1));
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.finished).toBe(true);
  });
});
