import { setupWorker } from "msw/browser";

import { createHandlers } from "./handlers";

const FRAME_DELAY_MS = 350;

/**
 * Starts the service worker mock for local dev and Playwright. It does nothing unless
 * `NEXT_PUBLIC_API_MOCKING=enabled`, so a production build never turns it on by accident.
 * Call it before the first render and await it.
 */
let started: Promise<void> | null = null;

export function enableApiMocking(): Promise<void> {
  if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") return Promise.resolve();
  started ??= setupWorker(...createHandlers({ streamFrameDelayMs: FRAME_DELAY_MS }))
    .start({ onUnhandledFrame: "bypass", quiet: true })
    .then(() => undefined);
  return started;
}
