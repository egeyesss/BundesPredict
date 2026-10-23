import type { Metadata } from "next";

import { loadTrackRecord } from "@/components/track-record/load";
import { TrackRecordView } from "@/components/track-record/TrackRecordView";

export const metadata: Metadata = {
  title: "Track record",
  description: "Frozen pre-kickoff predictions scored after the final whistle, next to the walk-forward backtest and the bookmakers' closing line.",
};

export default async function TrackRecordPage() {
  return <TrackRecordView outcome={await loadTrackRecord()} />;
}
