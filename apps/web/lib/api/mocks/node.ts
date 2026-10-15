import { setupServer } from "msw/node";

import { handlers } from "./handlers";

/** For Vitest and any other Node process. See `useApiMocks` for the lifecycle wiring. */
export const server = setupServer(...handlers);
