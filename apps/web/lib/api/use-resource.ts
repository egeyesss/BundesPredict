"use client";

import { useCallback, useEffect, useState } from "react";

/** A non-2xx answer or a network failure, flattened so views can switch on `status`. */
export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiFailure";
  }
}

export type Resource<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; failure: ApiFailure };

/**
 * Loads data in an effect. `key` identifies the request: when it changes the old answer is dropped,
 * and `null` means there is nothing to load yet.
 */
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, key: string | null) {
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<{ key: string | null; attempt: number; value: Resource<T> }>({
    key: null,
    attempt: 0,
    value: { status: "idle" },
  });

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setResource({ key, attempt, value: { status: "ready", data } });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        const failure = error instanceof ApiFailure ? error : new ApiFailure(0, "network_error", "The request did not complete.");
        setResource({ key, attempt, value: { status: "error", failure } });
      },
    );
    return () => controller.abort();
    // `load` is a fresh closure every render; `key` and `attempt` are what identify a request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const current: Resource<T> =
    key === null ? { status: "idle" } : resource.key === key && resource.attempt === attempt ? resource.value : { status: "loading" };
  const reload = useCallback(() => setAttempt((count) => count + 1), []);
  return { resource: current, reload };
}
