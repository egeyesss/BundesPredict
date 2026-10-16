import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SurfaceActive } from "./SurfaceActive";
import { Wordmark } from "./Wordmark";

function stubReducedMotion(reduced: boolean) {
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

const fakeContext = new Proxy(
  {},
  {
    get: (_, property) =>
      property === "measureText" ? () => ({ fontBoundingBoxAscent: 10, fontBoundingBoxDescent: 3 }) : () => {},
    set: () => true,
  },
) as CanvasRenderingContext2D;

beforeEach(() => {
  Object.defineProperty(document, "fonts", {
    configurable: true,
    value: {
      ready: Promise.resolve(),
      load: () => Promise.resolve([]),
      addEventListener: () => {},
      removeEventListener: () => {},
    },
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext as never);
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

describe("Wordmark", () => {
  it("server-renders the real text with no canvas", () => {
    const html = renderToString(<Wordmark />);
    expect(html).toContain("Bundes");
    expect(html).toContain("Predict");
    expect(html).not.toContain("<canvas");
  });

  it("renders BundesPredict as one text run for search and screen readers", () => {
    stubReducedMotion(true);
    const { container } = render(<Wordmark />);
    expect(container.textContent).toBe("BundesPredict");
  });

  it("mounts one aria-hidden canvas when motion is allowed", () => {
    stubReducedMotion(false);
    const { container } = render(<Wordmark />);
    const canvases = container.querySelectorAll("canvas");
    expect(canvases).toHaveLength(1);
    expect(canvases[0]).toHaveAttribute("aria-hidden", "true");
  });

  it("never mounts the canvas under prefers-reduced-motion", () => {
    stubReducedMotion(true);
    const { container } = render(<Wordmark size="hero" />);
    expect(container.querySelector("canvas")).toBeNull();
  });

  it("skips the canvas on an inactive surface such as a hidden island layer", () => {
    stubReducedMotion(false);
    const { container } = render(
      <SurfaceActive active={false}>
        <Wordmark />
      </SurfaceActive>,
    );
    expect(container.querySelector("canvas")).toBeNull();
    expect(container.textContent).toBe("BundesPredict");
  });

  it("mounts the canvas when the surface turns active", () => {
    stubReducedMotion(false);
    const { container, rerender } = render(
      <SurfaceActive active={false}>
        <Wordmark />
      </SurfaceActive>,
    );
    rerender(
      <SurfaceActive active>
        <Wordmark />
      </SurfaceActive>,
    );
    expect(container.querySelector("canvas")).not.toBeNull();
  });

  it("sizes the nav and hero variants differently", () => {
    stubReducedMotion(true);
    const { container, rerender } = render(<Wordmark size="nav" />);
    const navClass = (container.firstElementChild as HTMLElement).className;
    rerender(<Wordmark size="hero" />);
    expect((container.firstElementChild as HTMLElement).className).not.toBe(navClass);
    expect(screen.queryByRole("img")).toBeNull();
  });
});
