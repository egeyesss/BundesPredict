import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentEvent } from "@/lib/agent-state";

import { STREAMS } from "./streams";
import { useStreamReplay } from "./useStreamReplay";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const total = (name: keyof typeof STREAMS) => STREAMS[name].events.reduce((sum, [delay]) => sum + delay, 0);

describe("useStreamReplay", () => {
  it("delivers every event in order at its cumulative time", () => {
    const dispatch = vi.fn<(event: AgentEvent) => void>();
    const { result } = renderHook(() => useStreamReplay(dispatch));
    act(() => result.current.play(STREAMS.toolHeavy.events));
    expect(dispatch).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(total("toolHeavy"));
    });
    expect(dispatch.mock.calls.map(([event]) => event)).toEqual(STREAMS.toolHeavy.events.map(([, event]) => event));
  });

  it("starting a new replay cancels the one in flight", () => {
    const dispatch = vi.fn<(event: AgentEvent) => void>();
    const { result } = renderHook(() => useStreamReplay(dispatch));
    act(() => result.current.play(STREAMS.toolHeavy.events));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    dispatch.mockClear();
    act(() => result.current.play(STREAMS.withError.events));
    act(() => {
      vi.advanceTimersByTime(total("toolHeavy"));
    });
    const names = dispatch.mock.calls.map(([event]) => event.event);
    expect(names.filter((name) => name === "result")).toHaveLength(0);
    expect(names).toContain("error");
  });

  it("stops on unmount", () => {
    const dispatch = vi.fn();
    const { result, unmount } = renderHook(() => useStreamReplay(dispatch));
    act(() => result.current.play(STREAMS.toolHeavy.events));
    unmount();
    vi.advanceTimersByTime(total("toolHeavy"));
    expect(dispatch).not.toHaveBeenCalled();
  });
});
