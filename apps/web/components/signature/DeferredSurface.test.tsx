import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DeferredSurface } from "./DeferredSurface";
import { SurfaceActive, useSurfaceActive } from "./SurfaceActive";

function Probe() {
  return <span data-testid="probe">{String(useSurfaceActive())}</span>;
}

describe("DeferredSurface", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("reports its surface inactive until the page has settled", () => {
    render(
      <DeferredSurface delayMs={1000}>
        <Probe />
      </DeferredSurface>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("false");
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId("probe")).toHaveTextContent("true");
  });

  it("keeps an inner surface inactive while the outer one is", () => {
    render(
      <DeferredSurface delayMs={1000}>
        <SurfaceActive active>
          <Probe />
        </SurfaceActive>
      </DeferredSurface>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("false");
  });
});
