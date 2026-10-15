import { CSRF_COOKIE, CSRF_HEADER, readCookie } from "./client";
import { readPredictStream } from "./sse";
import type {
  ApiError,
  PredictRequest,
  PredictStreamEvent,
  QuotaExceededError,
} from "./types";

export const PREDICT_STREAM_PATH = "/api/v1/predict/stream";

export interface PredictStreamOptions {
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

export type PredictStreamStart =
  | { ok: true; events: AsyncGenerator<PredictStreamEvent> }
  /** A plain JSON failure before the first frame: 400, 401, 402, 429 or 503. */
  | { ok: false; status: number; error: ApiError | QuotaExceededError };

async function readError(response: Response): Promise<ApiError | QuotaExceededError> {
  const text = await response.text().catch(() => "");
  try {
    const body: unknown = JSON.parse(text);
    if (typeof body === "object" && body !== null && "code" in body && "message" in body) {
      return body as ApiError | QuotaExceededError;
    }
  } catch {
    // Fall through to the generic error below.
  }
  return { code: "unexpected_response", message: text || `The API answered ${response.status}.` };
}

/**
 * Starts the agent stream. openapi-fetch cannot stream a body, so this posts with plain fetch
 * and hands back either the typed event generator or the pre-stream JSON error.
 */
export async function startPredictStream(
  request: PredictRequest,
  { baseUrl = "", fetch, headers, signal }: PredictStreamOptions = {},
): Promise<PredictStreamStart> {
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Content-Type", "application/json");
  requestHeaders.set("Accept", "text/event-stream");
  const csrf =
    typeof document === "undefined" ? null : readCookie(document.cookie, CSRF_COOKIE);
  if (csrf !== null) requestHeaders.set(CSRF_HEADER, csrf);

  const send = fetch ?? globalThis.fetch;
  const response = await send(`${baseUrl}${PREDICT_STREAM_PATH}`, {
    method: "POST",
    headers: requestHeaders,
    body: JSON.stringify(request),
    credentials: "same-origin",
    signal,
  });

  if (!response.ok || response.body === null) {
    return { ok: false, status: response.status, error: await readError(response) };
  }
  return { ok: true, events: readPredictStream(response.body) };
}
