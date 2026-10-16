"use client";

import { useCallback, useEffect, useState } from "react";

/** A whole-second countdown for the rate-limit banner. `finished` stays true after it reaches zero. */
export function useCountdown() {
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [finished, setFinished] = useState(false);
  const [runId, setRunId] = useState(0);

  const active = secondsLeft > 0;

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      setSecondsLeft((left) => {
        if (left <= 1) setFinished(true);
        return Math.max(0, left - 1);
      });
    }, 1000);
    return () => clearInterval(timer);
    // A new run id restarts the interval so a restart keeps whole-second ticks.
  }, [active, runId]);

  const start = useCallback((seconds: number) => {
    setFinished(false);
    setSecondsLeft(seconds);
    setRunId((id) => id + 1);
  }, []);

  return { secondsLeft, active, finished, start };
}
