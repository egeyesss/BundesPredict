import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTypewriter } from "./use-typewriter";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const TEXT = "Without Kane, Bayern lose a lot of goals.";

describe("useTypewriter", () => {
  it("reveals the text progressively and calls onDone once at the end", () => {
    const onDone = vi.fn();
    const { result } = renderHook(() => useTypewriter(TEXT, { enabled: true, charsPerSecond: 90, onDone }));
    expect(result.current.visible).toBe("");
    expect(result.current.typing).toBe(true);

    act(() => vi.advanceTimersByTime(100));
    expect(result.current.visible.length).toBeGreaterThan(0);
    expect(result.current.visible.length).toBeLessThan(TEXT.length);
    expect(TEXT.startsWith(result.current.visible)).toBe(true);

    act(() => vi.advanceTimersByTime(2000));
    expect(result.current).toEqual({ visible: TEXT, typing: false });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("shows everything at once when disabled and still reports done", () => {
    const onDone = vi.fn();
    const { result } = renderHook(() => useTypewriter(TEXT, { enabled: false, charsPerSecond: 90, onDone }));
    expect(result.current).toEqual({ visible: TEXT, typing: false });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("types nothing for an empty text", () => {
    const { result } = renderHook(() => useTypewriter("", { enabled: true, charsPerSecond: 90 }));
    expect(result.current).toEqual({ visible: "", typing: false });
  });
});
