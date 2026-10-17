import * as Sentry from "@sentry/nextjs";

import { sentryRuntimeOptions } from "./lib/sentry";

/** Starts Sentry, and serves the API mocks to server-side fetches when `API_MOCKING=enabled`, for e2e runs and offline dev. */
export async function register() {
  Sentry.init(sentryRuntimeOptions(process.env.SENTRY_DSN_WEB));

  if (process.env.NEXT_RUNTIME !== "nodejs" || process.env.API_MOCKING !== "enabled") return;
  const { server } = await import("./lib/api/mocks/node");
  server.listen({ onUnhandledFrame: "bypass" });
}

export const onRequestError = Sentry.captureRequestError;
