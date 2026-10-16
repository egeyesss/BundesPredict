"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * Starts the MSW service worker before the app renders when `NEXT_PUBLIC_API_MOCKING` is
 * `enabled`, so client fetches never race the worker. With the flag off, which is every
 * production build, the dynamic import is dead code and children render immediately.
 */
export function ApiMockingGate({ children }: { children: ReactNode }) {
  const mocking = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
  const [ready, setReady] = useState(!mocking);

  useEffect(() => {
    let cancelled = false;
    if (process.env.NEXT_PUBLIC_API_MOCKING === "enabled") {
      import("@/lib/api/mocks/browser")
        .then(({ enableApiMocking }) => enableApiMocking())
        .then(() => {
          if (!cancelled) setReady(true);
        });
    }
    return () => {
      cancelled = true;
    };
  }, []);

  return ready ? children : null;
}
