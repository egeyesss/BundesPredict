"use client";

import { useCallback, useEffect, useRef } from "react";

import type { AgentEvent } from "@/lib/agent-state";

import type { TimedEvent } from "./streams";

/** Plays a timed event list into `dispatch`; starting a new replay cancels the one in flight. */
export function useStreamReplay(dispatch: (event: AgentEvent) => void) {
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const cancel = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const play = useCallback(
    (events: readonly TimedEvent[]) => {
      cancel();
      let elapsed = 0;
      timers.current = events.map(([delay, event]) => {
        elapsed += delay;
        return setTimeout(() => dispatch(event), elapsed);
      });
    },
    [cancel, dispatch],
  );

  useEffect(() => cancel, [cancel]);

  return { play, cancel };
}
