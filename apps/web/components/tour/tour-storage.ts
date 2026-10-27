import type { TourPhase, TourState } from "./tour-state";

const key = (userId: number) => `bp-tour:${userId}`;
const checkoutKey = (userId: number) => `bp-tour-checkout:${userId}`;

const PHASES: readonly TourPhase[] = ["welcome", "tour", "tip", "idle"];

function isTourState(value: unknown): value is TourState {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    PHASES.includes(candidate.phase as TourPhase) &&
    typeof candidate.index === "number" &&
    typeof candidate.answered === "boolean" &&
    typeof candidate.completed === "boolean"
  );
}

/** The saved tour for one demo user, or null when there is none or storage is unavailable. */
export function loadTour(userId: number): TourState | null {
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(key(userId)) ?? "null");
    if (!isTourState(parsed)) return null;
    return parsed.phase === "tip" ? { ...parsed, phase: "idle" } : parsed;
  } catch {
    return null;
  }
}

export function saveTour(userId: number, state: TourState): void {
  try {
    window.sessionStorage.setItem(key(userId), JSON.stringify(state.phase === "tip" ? { ...state, phase: "idle" } : state));
  } catch {
    // The tour keeps working from memory when storage is blocked.
  }
}

export function clearTour(userId: number): void {
  try {
    window.sessionStorage.removeItem(key(userId));
  } catch {
    // Nothing to clear.
  }
}

/** Set just before leaving for Stripe, so the return page can offer to pick the tour back up. */
export function markCheckoutStarted(userId: number): void {
  try {
    window.sessionStorage.setItem(checkoutKey(userId), "1");
  } catch {
    // Without storage the return page simply doesn't offer the resume.
  }
}

/** True once after a checkout was started; reading it clears it. */
export function takeCheckoutResume(userId: number): boolean {
  try {
    const started = window.sessionStorage.getItem(checkoutKey(userId)) === "1";
    if (started) window.sessionStorage.removeItem(checkoutKey(userId));
    return started;
  } catch {
    return false;
  }
}
