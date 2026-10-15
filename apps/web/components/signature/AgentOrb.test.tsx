import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OrbState } from "@/lib/agent-state";

import { AgentCaption } from "./AgentCaption";
import { AgentOrb } from "./AgentOrb";
import OrbCanvas from "./OrbCanvas";

function stubMotion(reduced: boolean) {
  vi.spyOn(window, "matchMedia").mockImplementation(
    (query) =>
      ({
        matches: reduced && query.includes("prefers-reduced-motion"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

const calls: string[] = [];
const fakeContext = new Proxy(
  {},
  {
    get: (_, property) => {
      if (property === "createRadialGradient") return () => ({ addColorStop: () => {} });
      return (...args: unknown[]) => {
        calls.push(String(property));
        return args;
      };
    },
    set: () => true,
  },
) as CanvasRenderingContext2D;

beforeEach(() => {
  calls.length = 0;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext as never);
  globalThis.ResizeObserver = class {
    constructor(private readonly callback: ResizeObserverCallback) {}
    observe(target: Element) {
      this.callback([{ target, contentRect: { width: 56, height: 56 } } as ResizeObserverEntry], this as never);
    }
    unobserve() {}
    disconnect() {}
  };
  globalThis.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
  Object.defineProperty(document, "fonts", {
    configurable: true,
    value: { ready: Promise.resolve(), load: () => Promise.resolve([]), addEventListener: () => {}, removeEventListener: () => {} },
  });
});
afterEach(() => vi.restoreAllMocks());

const thinking: OrbState = { phase: "thinking" };

describe("AgentOrb wrapper", () => {
  it("exposes the phase and tool so tests and styles can read them", () => {
    stubMotion(false);
    const { container, rerender } = render(<AgentOrb state={{ phase: "tool", tool: "get_weather", seq: 1 }} size={56} />);
    const orb = container.querySelector("[data-orb]") as HTMLElement;
    expect(orb).toHaveAttribute("data-orb-state", "tool");
    expect(orb).toHaveAttribute("data-orb-tool", "get_weather");
    rerender(<AgentOrb state={thinking} size={56} />);
    expect(orb).toHaveAttribute("data-orb-state", "thinking");
    expect(orb).not.toHaveAttribute("data-orb-tool");
  });

  it("is hidden from assistive tech; the caption carries the meaning", () => {
    stubMotion(false);
    const { container } = render(<AgentOrb state={thinking} size="message" />);
    expect(container.querySelector("[data-orb]")).toHaveAttribute("aria-hidden", "true");
  });

  it("maps named sizes to the locked pixel sizes", () => {
    stubMotion(false);
    const { container } = render(
      <>
        <AgentOrb state={thinking} size="chatHeader" />
        <AgentOrb state={thinking} size="message" />
        <AgentOrb state={thinking} size="stage" />
      </>,
    );
    const widths = [...container.querySelectorAll<HTMLElement>("[data-orb]")].map((orb) => orb.style.width);
    expect(widths).toEqual(["24px", "56px", "280px"]);
  });

  it("marks reduced motion so the ring colour carries the state", () => {
    stubMotion(true);
    const { container } = render(<AgentOrb state={thinking} size={56} />);
    expect(container.querySelector("[data-orb]")).toHaveAttribute("data-reduced", "true");
  });
});

describe("OrbCanvas", () => {
  it("draws one still frame and no animation loop under reduced motion", () => {
    stubMotion(true);
    const raf = vi.spyOn(window, "requestAnimationFrame");
    render(<OrbCanvas state={thinking} />);
    expect(calls).toContain("clearRect");
    expect(raf).not.toHaveBeenCalled();
  });

  it("redraws the still frame when the state changes under reduced motion", () => {
    stubMotion(true);
    const { rerender } = render(<OrbCanvas state={thinking} />);
    calls.length = 0;
    rerender(<OrbCanvas state={{ phase: "done" }} />);
    expect(calls).toContain("clearRect");
  });

  it("starts the shared frame loop when motion is allowed", () => {
    stubMotion(false);
    const raf = vi.spyOn(window, "requestAnimationFrame").mockReturnValue(1);
    render(<OrbCanvas state={thinking} />);
    expect(raf).toHaveBeenCalled();
  });

  it("falls back to the CSS orb when the 2d context is unavailable", () => {
    stubMotion(false);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = render(<OrbCanvas state={thinking} />);
    expect(container.querySelector("canvas")).toBeNull();
    expect(container.querySelector("[data-orb-fallback]")).not.toBeNull();
  });
});

describe("AgentCaption", () => {
  it("is a polite live region with the caption for the state", () => {
    const { rerender } = render(<AgentCaption state={{ phase: "tool", tool: "predict_match", seq: 1 }} />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Running the model");
    act(() => rerender(<AgentCaption state={{ phase: "error", message: "The model is unavailable." }} />));
    expect(region).toHaveTextContent("The model is unavailable.");
    expect(region).toHaveAttribute("data-state", "error");
  });

  it("stays mounted but empty when idle so later changes are announced", () => {
    render(<AgentCaption state={{ phase: "idle" }} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
