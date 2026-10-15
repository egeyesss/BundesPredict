"use client";

import { useIslandActivity } from "@/components/brand/IslandActivity";

import { Wordmark } from "./Wordmark";

/** The wordmark the app shell uses in the nav and footer: it speeds up while the agent runs. */
export function ShellWordmark() {
  const { agentCaption } = useIslandActivity();
  return <Wordmark size="nav" active={agentCaption !== null} />;
}
