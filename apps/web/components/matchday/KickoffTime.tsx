"use client";

import { useSyncExternalStore } from "react";

import { formatKickoff } from "@/lib/matchday";

const subscribe = () => () => {};

/**
 * Prints the kickoff in the viewer's timezone. The server cannot know it, so the server render
 * and the hydration pass show UTC and the browser's own zone replaces it right after.
 */
export function KickoffTime({ kickoffUtc, className }: { kickoffUtc: string; className?: string }) {
  const label = useSyncExternalStore(
    subscribe,
    () => formatKickoff(kickoffUtc),
    () => `${formatKickoff(kickoffUtc, { timeZone: "UTC", locale: "en-US" })} UTC`,
  );
  return (
    <time dateTime={kickoffUtc} className={className}>
      {label}
    </time>
  );
}
