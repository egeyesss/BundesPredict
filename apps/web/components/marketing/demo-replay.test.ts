import { describe, expect, it } from "vitest";

import { foldAgentState } from "@/lib/agent-state";
import type { PredictStreamEvent } from "@/lib/api/types";
import happy from "@/lib/api/mocks/recorded/streams/happy.json";

import { compactDemoStream, replayResult, replaySchedule } from "./demo-replay";

const stream = happy as unknown as PredictStreamEvent[];

describe("replaySchedule", () => {
  it("starts with the user's send and ends on the result", () => {
    const steps = replaySchedule(stream, { instant: false });
    expect(steps[0].event.event).toBe("send");
    expect(steps.at(-1)?.event.event).toBe("result");
  });

  it("leaves out frames that only matter to the chat page", () => {
    const names = replaySchedule(stream, { instant: false }).map((step) => step.event.event);
    expect(names).not.toContain("conversation");
    expect(names).not.toContain("quota");
  });

  it("paces the agent so the steps are readable but the whole run stays short", () => {
    const steps = replaySchedule(stream, { instant: false });
    const total = steps.reduce((sum, step) => sum + step.delayMs, 0);
    expect(steps.slice(1).every((step) => step.delayMs > 0)).toBe(true);
    expect(total).toBeGreaterThan(2000);
    expect(total).toBeLessThan(8000);
  });

  it("collapses to zero delays when motion is reduced", () => {
    expect(replaySchedule(stream, { instant: true }).every((step) => step.delayMs === 0)).toBe(true);
  });

  it("drives the orb through the tools and into done", () => {
    const events = replaySchedule(stream, { instant: true }).map((step) => step.event);
    const state = foldAgentState(events);
    expect(state.orb.phase).toBe("done");
    expect(state.stages.map((stage) => stage.status)).toEqual(["done", "done", "done"]);
  });
});

describe("compactDemoStream", () => {
  it("drops the score grids the landing page never shows", () => {
    const compact = compactDemoStream(stream);
    const result = compact.find((frame) => frame.event === "result");
    expect(result?.event === "result" && result.data.baseline?.score_grid).toEqual([]);
    expect(JSON.stringify(compact).length).toBeLessThan(JSON.stringify(stream).length);
  });
});

describe("replayResult", () => {
  it("returns the model and adjusted odds from the result frame", () => {
    const result = replayResult(stream);
    expect(result?.baseline?.p_home).toBeGreaterThan(result?.adjusted?.p_home ?? 1);
    expect(result?.adjustments).toHaveLength(1);
  });

  it("is null when the stream never produced a result", () => {
    expect(replayResult(stream.filter((frame) => frame.event !== "result"))).toBeNull();
  });
});
