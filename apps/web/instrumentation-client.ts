import * as Sentry from "@sentry/nextjs";

import { sentryRuntimeOptions } from "./lib/sentry";

Sentry.init(sentryRuntimeOptions(process.env.NEXT_PUBLIC_SENTRY_DSN_WEB));

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
