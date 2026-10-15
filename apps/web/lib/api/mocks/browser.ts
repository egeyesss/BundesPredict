import { setupWorker } from "msw/browser";

import { createHandlers } from "./handlers";

const FRAME_DELAY_MS = 350;

/**
 * Starts the service worker mock for local dev and Playwright. It does nothing unless
 * `NEXT_PUBLIC_API_MOCKING=enabled`, so a production build never turns it on by accident.
 * Call it before the first render and await it.
 */
export async function enableApiMocking(): Promise<void> {
  if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") return;
  const worker = setupWorker(...createHandlers({ streamFrameDelayMs: FRAME_DELAY_MS }));
  await worker.start({ onUnhandledFrame: "bypass" });
}
