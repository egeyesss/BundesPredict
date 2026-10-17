"use client";

import type { ReactNode } from "react";

import { useSession } from "@/components/account/SessionProvider";
import { navUserFromMe } from "@/lib/account/plan";

import { IslandNav } from "./IslandNav";

export function SessionIslandNav({ wordmark }: { wordmark: ReactNode }) {
  const { state } = useSession();
  const user = state.status === "ready" ? navUserFromMe(state.me) : null;
  return <IslandNav wordmark={wordmark} user={user} authPending={state.status === "loading"} />;
}
