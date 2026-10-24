"use client";

import Link from "next/link";

import { createApiClient } from "@/lib/api/client";
import type { TrackRecord } from "@/lib/api/types";
import { ApiFailure, useResource } from "@/lib/api/use-resource";
import { Skeleton } from "@/components/ui/skeleton";

import { BACKTEST_SUMMARY, liveRecordView } from "./track-record-teaser";

async function fetchTrackRecord(signal: AbortSignal): Promise<TrackRecord> {
  const { data, response } = await createApiClient({ baseUrl: window.location.origin }).GET("/api/v1/track-record", { signal });
  if (!response.ok || data === undefined) throw new ApiFailure(response.status, "track_record_unavailable", "The track record did not load.");
  return data;
}

function Stat({ label, value, note, children }: { label: string; value: string; note?: string; children?: React.ReactNode }) {
  return (
    <div className="grid content-start gap-1.5 rounded-xl border border-bp-border bg-bp-surface-1 p-5">
      <span className="text-sm text-bp-text-muted">{label}</span>
      <strong className="font-display text-[44px] leading-none font-bold tabular-nums">{value}</strong>
      {note && <span className="font-mono text-[13px] text-bp-text-muted">{note}</span>}
      {children}
    </div>
  );
}

function LiveCard({ resource }: { resource: ReturnType<typeof useResource<TrackRecord>>["resource"] }) {
  if (resource.status === "ready") {
    const view = liveRecordView(resource.data);
    if (view.kind === "scored") {
      return (
        <Stat label="Matches scored live this season" value={String(view.matches)}>
          <span className="font-mono text-[13px] text-bp-text-muted">{view.label}</span>
          <span className="font-mono text-[13px] text-bp-text-muted tabular-nums">
            model {view.modelRps.toFixed(4)}
            {view.bookmakerRps !== null && ` · bookmaker ${view.bookmakerRps.toFixed(4)}`}
          </span>
        </Stat>
      );
    }
    return (
      <Stat label="Live record" value="Backtest only">
        <span className="text-sm text-bp-text-muted">No live matches scored yet this season. Results are added after each matchday.</span>
      </Stat>
    );
  }
  if (resource.status === "error") {
    return (
      <Stat label="Live record" value="Unavailable">
        <span className="text-sm text-bp-text-muted">The live record is unavailable right now. The backtest figures are unaffected.</span>
      </Stat>
    );
  }
  return (
    <div role="status" aria-busy="true" aria-label="Loading the live record" className="grid content-start gap-3 rounded-xl border border-bp-border bg-bp-surface-1 p-5">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="h-11 w-28" />
      <Skeleton className="h-4 w-52" />
    </div>
  );
}

export function TrackRecordTeaser() {
  const { resource } = useResource(fetchTrackRecord, "track-record");
  return (
    <div className="grid gap-7">
      <div className="grid gap-3 min-[861px]:grid-cols-3">
        <Stat label="Matches backtested out of sample" value={BACKTEST_SUMMARY.matches.toLocaleString("en-US")} note={`${BACKTEST_SUMMARY.seasons} seasons, refit every gameweek`} />
        <Stat label="Model RPS" value={BACKTEST_SUMMARY.modelRps.toFixed(4)} note={`closing market ${BACKTEST_SUMMARY.marketRps.toFixed(4)}`} />
        <LiveCard resource={resource} />
      </div>
      <Link href="/track-record" className="w-fit border-b border-bp-border font-medium hover:border-bp-text">
        See the full track record →
      </Link>
    </div>
  );
}
