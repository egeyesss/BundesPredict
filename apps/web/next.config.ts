import { withSentryConfig } from "@sentry/nextjs/config";
import type { NextConfig } from "next";

import { sentryBuildOptions } from "./lib/sentry";

// /styleguide lives in page.styleguide.tsx, an extension that only exists in
// dev and Vercel preview builds, so production never even builds the route.
const styleguideEnabled =
  process.env.NODE_ENV !== "production" ||
  process.env.VERCEL_ENV === "preview" ||
  process.env.ENABLE_STYLEGUIDE === "1";

const nextConfig: NextConfig = {
  // The browser bundle needs the DSN at build time; it is public by design.
  env: { NEXT_PUBLIC_SENTRY_DSN_WEB: process.env.SENTRY_DSN_WEB ?? "" },
  // msw's package exports hide `msw/browser` from the server pass; the worker only ever runs in the browser.
  turbopack: {
    resolveAlias: { "msw/browser": "./node_modules/msw/lib/browser/index.js" },
  },
  pageExtensions: ["tsx", "ts", "jsx", "js", ...(styleguideEnabled ? ["styleguide.tsx"] : [])],
  // proxy.ts hands /accounts/* to Django, whose URLs end in a slash; stripping it here made the
  // Google callback bounce between this redirect and Django's APPEND_SLASH.
  skipTrailingSlashRedirect: true,
};

export default withSentryConfig(nextConfig, sentryBuildOptions(process.env));
