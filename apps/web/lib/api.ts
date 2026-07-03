// Typed client for the prediction API's SSE endpoint.
//
// The stream carries `stage` frames while the agent works (one per tool call /
// result), then a single `result` frame with the full prediction body, or an
// `error` frame if something broke after streaming began. EventSource can't
// POST, so this parses the SSE frames off a fetch body reader by hand.

export const API_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface Score {
  home: number;
  away: number;
  p: number;
}

export interface Markets {
  p_home: number;
  p_draw: number;
  p_away: number;
  p_over_2_5: number;
  p_under_2_5: number;
  p_btts: number;
  exp_home_goals: number;
  exp_away_goals: number;
  top_scores: Score[];
  // Full scoreline distribution, rows = home goals, columns = away goals.
  score_grid: number[][];
}

export interface AppliedAdjustment {
  factor: string;
  team: string | null;
  target: string;
  requested_magnitude_xg: number;
  effective_magnitude_xg: number;
  confidence: string;
  rationale: string;
}

export interface PredictResponse {
  home: string | null;
  away: string | null;
  explanation: string;
  baseline: Markets | null;
  adjusted: Markets | null;
  adjustments: AppliedAdjustment[];
  prediction_id: number | null;
}

export interface StageEvent {
  type: "tool_call" | "tool_result";
  name: string;
  input?: Record<string, unknown>;
  ok?: boolean;
  payload?: Record<string, unknown>;
}

export interface StreamCallbacks {
  onStage: (stage: StageEvent) => void;
  onResult: (result: PredictResponse) => void;
  onError: (message: string) => void;
}

/** POST the query and dispatch each SSE frame to the matching callback. */
export async function streamPredict(
  query: string,
  { onStage, onResult, onError }: StreamCallbacks,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/predict/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch {
    onError("Could not reach the prediction API. Is it running?");
    return;
  }

  if (!resp.ok || resp.body === null) {
    const detail = await resp.text().catch(() => "");
    onError(
      resp.status === 503
        ? "The model isn't ready to serve yet (no fitted parameters or no API key)."
        : `The API returned ${resp.status}. ${detail}`,
    );
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Frames are separated by a blank line; keep any trailing partial frame.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const event = frame
        .split("\n")
        .find((l) => l.startsWith("event: "))
        ?.slice("event: ".length);
      const data = frame
        .split("\n")
        .find((l) => l.startsWith("data: "))
        ?.slice("data: ".length);
      if (!event || !data) continue;

      if (event === "stage") {
        onStage(JSON.parse(data) as StageEvent);
      } else if (event === "result") {
        onResult(JSON.parse(data) as PredictResponse);
      } else if (event === "error") {
        const detail = (JSON.parse(data) as { detail?: string }).detail;
        onError(detail ?? "prediction failed");
      }
    }
  }
}
