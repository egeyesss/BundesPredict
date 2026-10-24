import { sentryRuntimeOptions } from "./lib/sentry";

const loadSentry = () => import("@sentry/nextjs");

/**
 * The SDK is about 380 KB of script, so it starts once the page has loaded instead of competing
 * with hydration. Errors thrown before that moment are not reported.
 */
function startSentryWhenIdle() {
  const start = () => void loadSentry().then((Sentry) => Sentry.init(sentryRuntimeOptions(process.env.NEXT_PUBLIC_SENTRY_DSN_WEB)));
  const afterLoad = () => ("requestIdleCallback" in window ? window.requestIdleCallback(start) : setTimeout(start, 1));
  if (document.readyState === "complete") afterLoad();
  else window.addEventListener("load", afterLoad, { once: true });
}

startSentryWhenIdle();

export const onRouterTransitionStart: typeof import("@sentry/nextjs").captureRouterTransitionStart = (...args) =>
  void loadSentry().then((Sentry) => Sentry.captureRouterTransitionStart(...args));
