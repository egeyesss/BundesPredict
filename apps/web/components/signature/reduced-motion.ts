import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void) {
  const query = window.matchMedia(QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

const read = () => window.matchMedia(QUERY).matches;

/**
 * `serverValue` is what the server render assumes. Canvas pieces pass `true` so the
 * server HTML never contains one; the tween passes `false` so it starts from the baseline.
 */
export function useReducedMotion(serverValue = false): boolean {
  return useSyncExternalStore(subscribe, read, () => serverValue);
}
