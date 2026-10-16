import { describe, expect, it } from "vitest";

import { readPredictStream } from "../sse";
import type { PredictStreamEvent } from "../types";
import { encodeSse, recordedStreams } from "./streams";

function bodyOf(text: string, chunkSize: number): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      for (let at = 0; at < bytes.length; at += chunkSize) {
        controller.enqueue(bytes.slice(at, at + chunkSize));
      }
      controller.close();
    },
  });
}

async function parse(text: string, chunkSize: number): Promise<PredictStreamEvent[]> {
  const events: PredictStreamEvent[] = [];
  for await (const event of readPredictStream(bodyOf(text, chunkSize))) events.push(event);
  return events;
}

const streams = Object.entries(recordedStreams);

describe.each(streams)("recorded stream %s", (_name, frames) => {
  const wire = encodeSse(frames);

  it.each([1, 7, 64, 1000, wire.length])("parses identically in %i byte chunks", async (size) => {
    expect(await parse(wire, size)).toEqual(frames);
  });

  it("opens with conversation and quota, and ends with exactly one terminal event", () => {
    expect(frames[0].event).toBe("conversation");
    expect(frames[1].event).toBe("quota");
    const terminals = frames.filter((f) => f.event === "result" || f.event === "error");
    expect(terminals).toHaveLength(1);
    expect(frames.at(-1)).toBe(terminals[0]);
  });

  it("pairs every tool_call with a tool_result of the same name, in order", () => {
    const stages = frames.flatMap((f) => (f.event === "stage" ? [f.data] : []));
    for (let i = 0; i < stages.length; i += 2) {
      expect(stages[i].type).toBe("tool_call");
      expect(stages[i + 1].type).toBe("tool_result");
      expect(stages[i + 1].name).toBe(stages[i].name);
    }
  });
});

describe("recorded results", () => {
  const results = streams.flatMap(([, frames]) =>
    frames.flatMap((f) => (f.event === "result" ? [f.data] : [])),
  );

  it("exist for the happy path, the tool-heavy path and the last free chat", () => {
    expect(results).toHaveLength(3);
  });

  it.each(results.map((r) => [`${r.home} v ${r.away}`, r] as const))(
    "%s carries consistent markets",
    (_label, result) => {
      for (const markets of [result.baseline, result.adjusted]) {
        expect(markets).not.toBeNull();
        if (markets === null) continue;
        expect(markets.p_home + markets.p_draw + markets.p_away).toBeCloseTo(1, 3);
        expect(markets.score_grid).toHaveLength(11);
        const total = markets.score_grid.flat().reduce((sum, p) => sum + p, 0);
        expect(total).toBeCloseTo(1, 4);
      }
      expect(result.adjustments.length).toBeGreaterThan(0);
      expect(result.prediction_id).not.toBeNull();
    },
  );

  it("the happy path lowers Dortmund's win probability after the injury news", () => {
    const happy = results[0];
    expect(happy.adjusted?.p_home).toBeLessThan(happy.baseline?.p_home ?? 0);
  });
});

describe("encodeSse", () => {
  it("writes event and data lines separated by a blank line", () => {
    const text = encodeSse([
      { event: "quota", data: { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" } },
    ]);
    expect(text).toBe(
      'event: quota\ndata: {"used":1,"limit":3,"resets_at":"2026-10-16T00:00:00Z"}\n\n',
    );
  });
});
