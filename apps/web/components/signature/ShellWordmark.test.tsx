import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IslandActivityProvider, useIslandActivity } from "@/components/brand/IslandActivity";
import { IslandNav } from "@/components/brand/IslandNav";

import { ShellWordmark } from "./ShellWordmark";

vi.mock("next/navigation", () => ({ usePathname: () => "/matchday" }));

const fakeContext = new Proxy(
  {},
  { get: (_, property) => (property === "measureText" ? () => ({ fontBoundingBoxAscent: 10, fontBoundingBoxDescent: 3 }) : () => {}), set: () => true },
) as CanvasRenderingContext2D;

function setWidth(width: number, scrollY = 0) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "scrollY", { configurable: true, value: scrollY });
}

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext as never);
  Object.defineProperty(document, "fonts", {
    configurable: true,
    value: { ready: Promise.resolve(), load: () => Promise.resolve([]), addEventListener: () => {}, removeEventListener: () => {} },
  });
  globalThis.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
});
afterEach(() => vi.restoreAllMocks());

const island = () => document.querySelector("nav.island") as HTMLElement;
const canvasesIn = (layer: string) => island().querySelector(`[data-layer="${layer}"]`)!.querySelectorAll("canvas").length;

describe("the island's wordmark", () => {
  it("mounts a canvas only in the visible layer", async () => {
    setWidth(1440, 0);
    render(
      <IslandActivityProvider>
        <IslandNav wordmark={<ShellWordmark />} user={null} />
      </IslandActivityProvider>,
    );
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    expect(island().querySelectorAll("canvas")).toHaveLength(1);
    expect(canvasesIn("full")).toBe(1);
  });

  it("moves the canvas to the compact layer once the page scrolls", async () => {
    setWidth(1440, 0);
    render(
      <IslandActivityProvider>
        <IslandNav wordmark={<ShellWordmark />} user={null} />
      </IslandActivityProvider>,
    );
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    act(() => {
      setWidth(1440, 400);
      window.dispatchEvent(new Event("scroll"));
    });
    await waitFor(() => expect(canvasesIn("compact")).toBe(1));
    expect(canvasesIn("full")).toBe(0);
    expect(island().querySelectorAll("canvas")).toHaveLength(1);
  });

  it("keeps real text in every layer", async () => {
    setWidth(1440, 0);
    render(
      <IslandActivityProvider>
        <IslandNav wordmark={<ShellWordmark />} user={null} />
      </IslandActivityProvider>,
    );
    for (const layer of ["full", "compact", "mobile", "open"]) {
      expect(island().querySelector(`[data-layer="${layer}"] .isl-logo`)?.textContent).toBe("BundesPredict");
    }
  });
});

describe("ShellWordmark", () => {
  it("turns active while the agent has a caption", async () => {
    function Controls() {
      const { setAgentCaption } = useIslandActivity();
      return (
        <>
          <button onClick={() => setAgentCaption("Running the model")}>start</button>
          <button onClick={() => setAgentCaption(null)}>stop</button>
        </>
      );
    }
    const { container } = render(
      <IslandActivityProvider>
        <ShellWordmark />
        <Controls />
      </IslandActivityProvider>,
    );
    const mark = container.querySelector("[data-size]")!;
    expect(mark).toHaveAttribute("data-active", "false");
    await userEvent.click(screen.getByText("start"));
    expect(mark).toHaveAttribute("data-active", "true");
    await userEvent.click(screen.getByText("stop"));
    expect(mark).toHaveAttribute("data-active", "false");
  });
});
