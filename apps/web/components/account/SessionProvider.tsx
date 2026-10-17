"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { browserTimeZone } from "@/lib/account/timezone";
import { fetchMe, updateMe } from "@/lib/api/browser";
import type { Me } from "@/lib/api/types";
import { ApiFailure } from "@/lib/api/use-resource";

export type SessionState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "error" }
  | { status: "ready"; me: Me };

type SessionContextValue = {
  state: SessionState;
  /** Re-reads `/me`, for after a payment or a profile change made elsewhere. */
  refresh: () => Promise<void>;
  /** Puts an account the page already holds (a PATCH answer) into the shared state. */
  setMe: (me: Me) => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession needs a SessionProvider above it.");
  return value;
}

async function loadSession(signal?: AbortSignal): Promise<SessionState> {
  try {
    return { status: "ready", me: await fetchMe(signal ?? new AbortController().signal) };
  } catch (error) {
    return error instanceof ApiFailure && error.status === 401 ? { status: "signed_out" } : { status: "error" };
  }
}

/** One `/me` read per page load feeds the nav and anything else that needs to know who is signed in. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const reportedTimeZone = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    loadSession(controller.signal).then((next) => {
      if (!controller.signal.aborted) setState(next);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (state.status !== "ready" || reportedTimeZone.current) return;
    reportedTimeZone.current = true;
    const zone = browserTimeZone();
    if (!zone || zone === state.me.timezone) return;
    // No source: the backend ignores this report when the user has pinned a zone by hand.
    updateMe({ timezone: zone }).then(
      (me) => setState({ status: "ready", me }),
      () => undefined,
    );
  }, [state]);

  const refresh = useCallback(async () => setState(await loadSession()), []);
  const setMe = useCallback((me: Me) => setState({ status: "ready", me }), []);
  const value = useMemo(() => ({ state, refresh, setMe }), [state, refresh, setMe]);

  return <SessionContext value={value}>{children}</SessionContext>;
}
