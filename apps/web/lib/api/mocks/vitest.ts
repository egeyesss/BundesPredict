import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./node";
import { clearMockSession, resetMeChanges } from "./session";
import { mockUsage } from "./state";

/**
 * Call once at the top of a test file to serve the contract mocks. Requests with no handler
 * fail the test instead of reaching the network, and per-test `server.use(...)` overrides are
 * undone after every test.
 */
export function setupApiMocks(): void {
  beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
  afterEach(() => {
    server.resetHandlers();
    mockUsage.reset();
    clearMockSession();
    resetMeChanges();
  });
  afterAll(() => server.close());
}
