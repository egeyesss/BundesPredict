import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 520px)";

function subscribe(onChange: () => void) {
  const query = window.matchMedia(QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True under the 520px breakpoint the chat layout already collapses at; the server render assumes wide. */
export function useNarrowScreen(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => false);
}
