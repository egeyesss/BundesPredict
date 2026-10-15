import type { PredictStreamEvent } from "./types";

export interface RawSseFrame {
  event: string;
  data: string;
}

export interface SseParser {
  /** Feeds the next chunk of text and returns every frame it completed. */
  push(chunk: string): RawSseFrame[];
}

export class SseProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SseProtocolError";
  }
}

const LINE_END = /\r\n|\r|\n/g;

/**
 * Incremental parser for the `text/event-stream` wire format.
 *
 * Chunks can end anywhere, so unfinished lines stay buffered. A trailing `\r` is held back until
 * the next chunk shows whether it is the first half of `\r\n`. A frame that never receives its
 * blank line is dropped, as the SSE spec says.
 */
export function createSseParser(): SseParser {
  let buffer = "";
  let atStart = true;
  let eventName = "";
  let dataLines: string[] = [];

  function handleLine(line: string, frames: RawSseFrame[]): void {
    if (line === "") {
      if (dataLines.length > 0) {
        frames.push({ event: eventName || "message", data: dataLines.join("\n") });
      }
      eventName = "";
      dataLines = [];
      return;
    }
    if (line.startsWith(":")) return;

    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "event") eventName = value;
    else if (field === "data") dataLines.push(value);
  }

  return {
    push(chunk) {
      buffer += chunk;
      if (atStart && buffer.length > 0) {
        if (buffer.startsWith("﻿")) buffer = buffer.slice(1);
        atStart = false;
      }

      const frames: RawSseFrame[] = [];
      let lineStart = 0;
      LINE_END.lastIndex = 0;
      for (let match = LINE_END.exec(buffer); match !== null; match = LINE_END.exec(buffer)) {
        const endsWithBareCr = match[0] === "\r" && match.index + 1 === buffer.length;
        if (endsWithBareCr) break;
        handleLine(buffer.slice(lineStart, match.index), frames);
        lineStart = match.index + match[0].length;
      }
      buffer = buffer.slice(lineStart);
      return frames;
    },
  };
}

const STAGE_TYPES = new Set(["tool_call", "tool_result"]);

function decodeObject(raw: RawSseFrame): Record<string, unknown> {
  let value: unknown;
  try {
    value = JSON.parse(raw.data);
  } catch {
    throw new SseProtocolError(`The "${raw.event}" event carried invalid JSON.`);
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new SseProtocolError(`The "${raw.event}" event did not carry a JSON object.`);
  }
  return value as Record<string, unknown>;
}

/**
 * Turns a raw frame into one of the five contract events, or null for any other event name so
 * the server can add events without breaking older clients. The payload is trusted to match the
 * schema beyond being an object (and a known `type` for stage events).
 */
export function parsePredictFrame(raw: RawSseFrame): PredictStreamEvent | null {
  switch (raw.event) {
    case "conversation":
    case "quota":
    case "result":
    case "error":
      return { event: raw.event, data: decodeObject(raw) } as PredictStreamEvent;
    case "stage": {
      const data = decodeObject(raw);
      if (typeof data.type !== "string" || !STAGE_TYPES.has(data.type)) {
        throw new SseProtocolError(`Unknown stage type "${String(data.type)}".`);
      }
      return { event: "stage", data } as PredictStreamEvent;
    }
    default:
      return null;
  }
}

/** Reads a response body as a sequence of typed contract events. Independent of React. */
export async function* readPredictStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<PredictStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const raw of parser.push(decoder.decode(value, { stream: true }))) {
        const event = parsePredictFrame(raw);
        if (event !== null) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
