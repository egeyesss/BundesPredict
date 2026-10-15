import { afterEach, describe, expect, it, vi } from "vitest";

import { OrbEngine } from "./orb-engine";

type Call = [string, ...unknown[]];

function recordingCanvas() {
  const calls: Call[] = [];
  const context = new Proxy(
    {},
    {
      get: (_, property) => {
        if (property === "createRadialGradient") return () => ({ addColorStop: () => {} });
        return (...args: unknown[]) => calls.push([String(property), ...args]);
      },
      set: (_, property, value) => {
        calls.push([`set ${String(property)}`, value]);
        return true;
      },
    },
  ) as CanvasRenderingContext2D;
  const canvas = document.createElement("canvas");
  vi.spyOn(canvas, "getContext").mockReturnValue(context as never);
  return { canvas, calls };
}

afterEach(() => vi.restoreAllMocks());

const drawnText = (calls: Call[]) => calls.filter(([name]) => name === "fillText").map((call) => `${call[1]}@${call[2]},${call[3]}`);

describe("OrbEngine still mode", () => {
  it("draws the same frame every time for the same state", () => {
    const frame = (at: number) => {
      const { canvas, calls } = recordingCanvas();
      const engine = new OrbEngine(canvas, true);
      engine.resize(280);
      engine.setState({ phase: "done" }, at);
      engine.snap();
      engine.draw(at + 37);
      return drawnText(calls);
    };
    const first = frame(1000);
    expect(first.length).toBeGreaterThan(300);
    expect(frame(98765)).toEqual(first);
  });

  it("does not jitter on error", () => {
    const frame = () => {
      const { canvas, calls } = recordingCanvas();
      const engine = new OrbEngine(canvas, true);
      engine.resize(280);
      engine.setState({ phase: "error", message: "x" }, 5);
      engine.snap();
      engine.draw(5);
      return drawnText(calls);
    };
    expect(frame()).toEqual(frame());
  });
});

describe("OrbEngine animated mode", () => {
  it("draws dots instead of glyphs below 6px glyph size", () => {
    const { canvas, calls } = recordingCanvas();
    const engine = new OrbEngine(canvas);
    engine.resize(56);
    engine.draw(0);
    expect(calls.some(([name]) => name === "fillText")).toBe(false);
    expect(calls.filter(([name]) => name === "fillRect").length).toBeGreaterThan(100);
  });

  it("draws glyphs at the stage size", () => {
    const { canvas, calls } = recordingCanvas();
    const engine = new OrbEngine(canvas);
    engine.resize(280);
    engine.draw(0);
    expect(calls.filter(([name]) => name === "fillText")).toHaveLength(380);
  });

  it("sizes the backing store by devicePixelRatio, capped at 2", () => {
    vi.stubGlobal("devicePixelRatio", 3);
    const { canvas } = recordingCanvas();
    new OrbEngine(canvas).resize(100);
    expect(canvas.width).toBe(200);
    vi.unstubAllGlobals();
  });

  it("does not draw before it has a size", () => {
    const { canvas, calls } = recordingCanvas();
    new OrbEngine(canvas).draw(0);
    expect(calls).toHaveLength(0);
  });
});
