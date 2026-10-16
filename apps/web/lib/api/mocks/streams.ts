import error from "./recorded/streams/error.json";
import happy from "./recorded/streams/happy.json";
import lastChat from "./recorded/streams/last-chat.json";
import toolHeavy from "./recorded/streams/tool-heavy.json";
import type { PredictStreamEvent } from "../types";

/**
 * Streams recorded from the real engine by scripts/record_mock_streams.py. The JSON files are
 * generated; regenerate them instead of editing.
 */
export const recordedStreams = {
  happy: happy as unknown as PredictStreamEvent[],
  tool_heavy: toolHeavy as unknown as PredictStreamEvent[],
  last_chat: lastChat as unknown as PredictStreamEvent[],
  error: error as unknown as PredictStreamEvent[],
};

export type RecordedStreamName = keyof typeof recordedStreams;

/** The wire format the Django view writes: `event: <name>`, `data: <json>`, blank line. */
export function encodeSse(events: readonly PredictStreamEvent[]): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join("");
}

export interface SseResponseOptions {
  /** Pause before each frame after the first, so the UI shows the agent working. */
  frameDelayMs?: number;
}

/** A streaming `text/event-stream` response that releases one frame at a time. */
export function sseResponse(
  events: readonly PredictStreamEvent[],
  { frameDelayMs = 0 }: SseResponseOptions = {},
): Response {
  const encoder = new TextEncoder();
  let next = 0;
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) {
      if (next >= events.length) {
        controller.close();
        return;
      }
      if (next > 0 && frameDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, frameDelayMs));
      }
      controller.enqueue(encoder.encode(encodeSse([events[next]])));
      next += 1;
    },
  });
  return new Response(body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
