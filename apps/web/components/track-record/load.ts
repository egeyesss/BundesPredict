import type { TrackRecord } from "@/lib/api/types";

export type TrackRecordOutcome = { status: "ok"; record: TrackRecord } | { status: "error" };

/** Scores change once a day, so a few minutes of reuse costs nothing. */
export const TRACK_RECORD_REVALIDATE_SECONDS = 300;

/** Fetches the public track record on the server. Never throws: the page shows its error state instead. */
export async function loadTrackRecord(): Promise<TrackRecordOutcome> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/track-record`, {
      headers: { "x-proxy-secret": process.env.PROXY_SECRET ?? "" },
      next: { revalidate: TRACK_RECORD_REVALIDATE_SECONDS },
    });
    if (!response.ok) return { status: "error" };
    return { status: "ok", record: (await response.json()) as TrackRecord };
  } catch {
    return { status: "error" };
  }
}
