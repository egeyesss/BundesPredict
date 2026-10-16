/** Options shared by the server, edge and browser `Sentry.init` calls. No DSN means no reporting. */
export function sentryRuntimeOptions(dsn: string | undefined) {
  return { dsn, enabled: Boolean(dsn), sendDefaultPii: false };
}

/** Options for `withSentryConfig`. Source maps upload only when an auth token is available. */
export function sentryBuildOptions(env: Record<string, string | undefined>) {
  return {
    org: env.SENTRY_ORG ?? "ege-yesilyurt",
    project: env.SENTRY_PROJECT ?? "bundespredict-web",
    authToken: env.SENTRY_AUTH_TOKEN,
    sourcemaps: { disable: !env.SENTRY_AUTH_TOKEN },
    telemetry: false,
    silent: !env.CI,
  };
}
