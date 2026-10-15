import { describe, expect, it } from "vitest";

import {
  SseProtocolError,
  createSseParser,
  parsePredictFrame,
  readPredictStream,
  type RawSseFrame,
} from "./sse";
import type { PredictStreamEvent } from "./types";

function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function parseAll(chunks: string[]): RawSseFrame[] {
  const parser = createSseParser();
  return chunks.flatMap((chunk) => parser.push(chunk));
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<PredictStreamEvent[]> {
  const events: PredictStreamEvent[] = [];
  for await (const event of readPredictStream(stream)) events.push(event);
  return events;
}

describe("createSseParser", () => {
  const wire = `${frame("quota", { used: 1, limit: 3 })}${frame("stage", { type: "tool_call" })}`;
  const expected: RawSseFrame[] = [
    { event: "quota", data: '{"used":1,"limit":3}' },
    { event: "stage", data: '{"type":"tool_call"}' },
  ];

  it("parses whole frames", () => {
    expect(parseAll([wire])).toEqual(expected);
  });

  it("gives the same frames for a split at every possible position", () => {
    for (let cut = 0; cut <= wire.length; cut += 1) {
      expect(parseAll([wire.slice(0, cut), wire.slice(cut)])).toEqual(expected);
    }
  });

  it("gives the same frames when fed one character at a time", () => {
    expect(parseAll([...wire])).toEqual(expected);
  });

  it("handles CRLF line endings, including a CRLF split between chunks", () => {
    const crlf = wire.replaceAll("\n", "\r\n");
    expect(parseAll([crlf])).toEqual(expected);
    for (let cut = 0; cut <= crlf.length; cut += 1) {
      expect(parseAll([crlf.slice(0, cut), crlf.slice(cut)])).toEqual(expected);
    }
  });

  it("handles lone CR line endings", () => {
    // A final bare CR could still become CRLF, so the parser waits for one more byte.
    expect(parseAll([wire.replaceAll("\n", "\r"), ":"])).toEqual(expected);
  });

  it("ignores comment lines and heartbeats", () => {
    const withComments = `: keep-alive\n\n${frame("quota", { used: 1, limit: 3 })}:\n: another\n`;
    expect(parseAll([withComments])).toEqual([expected[0]]);
  });

  it("joins multi-line data with newlines", () => {
    const multi = "event: result\ndata: {\ndata:   \"a\": 1\ndata: }\n\n";
    expect(parseAll([multi])).toEqual([{ event: "result", data: '{\n  "a": 1\n}' }]);
  });

  it("strips one leading space after the colon and no more", () => {
    expect(parseAll(["event: x\ndata:  two\n\n"])).toEqual([{ event: "x", data: " two" }]);
    expect(parseAll(["event:x\ndata:one\n\n"])).toEqual([{ event: "x", data: "one" }]);
  });

  it("defaults the event name to message", () => {
    expect(parseAll(["data: hello\n\n"])).toEqual([{ event: "message", data: "hello" }]);
  });

  it("does not dispatch a frame without data", () => {
    expect(parseAll(["event: quota\n\n"])).toEqual([]);
  });

  it("does not leak the event name into the next frame", () => {
    expect(parseAll(["event: a\ndata: 1\n\ndata: 2\n\n"])).toEqual([
      { event: "a", data: "1" },
      { event: "message", data: "2" },
    ]);
  });

  it("ignores id and retry fields and unknown fields", () => {
    expect(parseAll(["id: 7\nretry: 1000\nfoo: bar\nevent: a\ndata: 1\n\n"])).toEqual([
      { event: "a", data: "1" },
    ]);
  });

  it("drops a frame that never got its blank line", () => {
    expect(parseAll(["event: a\ndata: 1\n"])).toEqual([]);
  });

  it("skips a byte order mark at the start of the stream", () => {
    expect(parseAll(["﻿event: a\ndata: 1\n\n"])).toEqual([{ event: "a", data: "1" }]);
  });
});

describe("parsePredictFrame", () => {
  it("wraps each of the five contract events with its decoded payload", () => {
    const cases: PredictStreamEvent[] = [
      { event: "conversation", data: { id: null, title: "Kane is out" } },
      { event: "quota", data: { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" } },
      { event: "stage", data: { type: "tool_call", name: "predict_match", input: { home: "A" } } },
      {
        event: "stage",
        data: { type: "tool_result", name: "predict_match", ok: true, summary: "62% / 21% / 17%" },
      },
      { event: "error", data: { code: "agent_failed", message: "Prediction failed." } },
    ];
    for (const expected of cases) {
      const raw = { event: expected.event, data: JSON.stringify(expected.data) };
      expect(parsePredictFrame(raw)).toEqual(expected);
    }
  });

  it("narrows on event and on the stage type", () => {
    const parsed = parsePredictFrame({
      event: "stage",
      data: JSON.stringify({ type: "tool_result", name: "t", ok: false, summary: "s" }),
    });
    if (parsed?.event !== "stage") throw new Error("expected a stage event");
    if (parsed.data.type !== "tool_result") throw new Error("expected a tool_result");
    expect(parsed.data.ok).toBe(false);
  });

  it("returns null for event names the contract does not define", () => {
    expect(parsePredictFrame({ event: "ping", data: "{}" })).toBeNull();
    expect(parsePredictFrame({ event: "message", data: "hi" })).toBeNull();
  });

  it("throws on malformed JSON in a known event", () => {
    expect(() => parsePredictFrame({ event: "quota", data: "{oops" })).toThrow(SseProtocolError);
  });

  it("throws when the payload is not an object", () => {
    expect(() => parsePredictFrame({ event: "quota", data: "3" })).toThrow(SseProtocolError);
    expect(() => parsePredictFrame({ event: "quota", data: "null" })).toThrow(SseProtocolError);
  });

  it("throws on a stage payload with an unknown type", () => {
    const raw = { event: "stage", data: JSON.stringify({ type: "thinking" }) };
    expect(() => parsePredictFrame(raw)).toThrow(SseProtocolError);
  });
});

describe("readPredictStream", () => {
  const body =
    frame("conversation", { id: "6f1c", title: "t" }) +
    frame("quota", { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" }) +
    frame("error", { code: "agent_failed", message: "Prediction failed." });

  it("yields typed events in order", async () => {
    const events = await collect(streamOf([body]));

    expect(events.map((e) => e.event)).toEqual(["conversation", "quota", "error"]);
  });

  it("copes with a multi-byte character split across chunks", async () => {
    const bytes = new TextEncoder().encode(frame("conversation", { id: null, title: "Köln v Düsseldorf" }));
    const cut = bytes.indexOf(0xc3) + 1;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, cut));
        controller.enqueue(bytes.slice(cut));
        controller.close();
      },
    });

    const events = await collect(stream);

    expect(events).toEqual([
      { event: "conversation", data: { id: null, title: "Köln v Düsseldorf" } },
    ]);
  });

  it("skips unknown events and heartbeats without ending the stream", async () => {
    const events = await collect(
      streamOf([": hb\n\n", frame("ping", {}), frame("quota", { used: 2, limit: 3 })]),
    );

    expect(events.map((e) => e.event)).toEqual(["quota"]);
  });

  it("rejects when a known event carries malformed JSON", async () => {
    await expect(collect(streamOf(["event: quota\ndata: {nope\n\n"]))).rejects.toBeInstanceOf(
      SseProtocolError,
    );
  });
});
