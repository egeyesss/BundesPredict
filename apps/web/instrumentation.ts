/** Serves the API mocks to server-side fetches when `API_MOCKING=enabled`, for e2e runs and offline dev. */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs" || process.env.API_MOCKING !== "enabled") return;
  const { server } = await import("./lib/api/mocks/node");
  server.listen({ onUnhandledFrame: "bypass" });
}
