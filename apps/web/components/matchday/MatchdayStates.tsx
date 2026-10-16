"use client";

import { Pause, RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

function SkeletonCard() {
  return (
    <div data-slot="skeleton-card" className="grid gap-3 rounded-[var(--bp-radius)] border border-bp-border bg-bp-surface-1 px-4 py-3.5">
      <div className="flex justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2.5">
        <span className="flex items-center gap-2">
          <Skeleton className="size-8 rounded-full" />
          <Skeleton className="h-5 w-20" />
        </span>
        <Skeleton className="h-3 w-2" />
        <span className="flex items-center justify-end gap-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="size-8 rounded-full" />
        </span>
      </div>
      <div className="grid gap-1.5">
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-3 w-full" />
      </div>
      <div className="flex justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-36" />
      </div>
    </div>
  );
}

/** Six cards the size of real ones, so nothing jumps when the fixtures land. */
export function MatchdaySkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading fixtures" className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-3">
      {Array.from({ length: 6 }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

export function MatchdayEmpty() {
  return (
    <StateMessage
      icon={<Pause className="size-4" />}
      title="No Bundesliga matches this week"
      actions={
        <Button asChild variant="secondary">
          <Link href="/track-record">See last matchday&apos;s results</Link>
        </Button>
      }
    >
      The league may be paused for an international break. Odds for the next matchday appear here on the Monday before it, after the refit.
    </StateMessage>
  );
}

export function MatchdayError() {
  const router = useRouter();
  return (
    <StateMessage
      tone="crit"
      icon={<X className="size-4" />}
      title="Couldn't load this week's fixtures"
      actions={
        <>
          <Button onClick={() => router.refresh()}>
            <RefreshCw /> Retry
          </Button>
          <span className="font-mono text-xs text-bp-text-muted">or reload the page</span>
        </>
      }
    >
      The connection to our server failed. Your chats and account are fine.
    </StateMessage>
  );
}
