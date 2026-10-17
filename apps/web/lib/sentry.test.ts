import { describe, expect, it } from "vitest";

import { sentryBuildOptions, sentryRuntimeOptions } from "./sentry";

describe("sentryRuntimeOptions", () => {
  it("stays disabled without a DSN", () => {
    expect(sentryRuntimeOptions(undefined)).toMatchObject({ enabled: false });
    expect(sentryRuntimeOptions("")).toMatchObject({ enabled: false });
  });

  it("turns on with a DSN and keeps personal data out of events", () => {
    expect(sentryRuntimeOptions("https://key@o1.ingest.sentry.io/2")).toEqual({
      dsn: "https://key@o1.ingest.sentry.io/2",
      enabled: true,
      sendDefaultPii: false,
    });
  });
});

describe("sentryBuildOptions", () => {
  it("skips the source map upload when there is no auth token", () => {
    expect(sentryBuildOptions({}).sourcemaps).toEqual({ disable: true });
  });

  it("uploads source maps when the auth token is present", () => {
    const options = sentryBuildOptions({
      SENTRY_AUTH_TOKEN: "token",
      SENTRY_ORG: "my-org",
      SENTRY_PROJECT: "my-project",
    });

    expect(options.sourcemaps).toEqual({ disable: false });
    expect(options).toMatchObject({ authToken: "token", org: "my-org", project: "my-project" });
  });

  it("never sends build telemetry to Sentry", () => {
    expect(sentryBuildOptions({}).telemetry).toBe(false);
  });
});
