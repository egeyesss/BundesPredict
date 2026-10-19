import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useNarrowScreen } from "./use-narrow-screen";

function stubMatchMedia(initial: boolean) {
  let matches = initial;
  const listeners = new Set<() => void>();
  vi.stubGlobal("matchMedia", (query: string) => ({
    get matches() {
      return matches;
    },
    media: query,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }));
  return (next: boolean) => {
    matches = next;
    listeners.forEach((listener) => listener());
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("useNarrowScreen", () => {
  it("is true on a phone-width screen", () => {
    stubMatchMedia(true);
    expect(renderHook(() => useNarrowScreen()).result.current).toBe(true);
  });

  it("follows the screen when it is resized", () => {
    const setMatches = stubMatchMedia(false);
    const { result } = renderHook(() => useNarrowScreen());
    expect(result.current).toBe(false);

    act(() => setMatches(true));

    expect(result.current).toBe(true);
  });
});
