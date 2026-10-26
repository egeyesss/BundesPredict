"use client";

import { createContext, useContext } from "react";

import type { FixtureDetail } from "@/lib/api/types";

export type ChatStatus = "empty" | "busy" | "done" | "failed";

/** What the chat page tells the tour, and the two things the tour may ask of it. */
export type TourChatHandle = {
  status: ChatStatus;
  /** A message is typed and nothing blocks sending it. */
  canSend: boolean;
  outOfChats: boolean;
  /** The transcript on screen is a recording, not a live answer. */
  recorded: boolean;
  send: () => void;
  replay: () => void;
};

export type TourChatLink = {
  /** True while a chat stop is showing, which is when the chat should offer the suggested message. */
  wantsDraft: boolean;
  register: (handle: TourChatHandle | null) => void;
};

export const TourChatLinkContext = createContext<TourChatLink | null>(null);

/** Null outside a demo session, so the chat behaves exactly as before for everyone else. */
export function useTourChatLink(): TourChatLink | null {
  return useContext(TourChatLinkContext);
}

/** A what-if built from the pinned fixture's real club name; it never claims anyone is injured. */
export function suggestedMessage(fixture: Pick<FixtureDetail, "home">): string {
  return `What if ${fixture.home.name}'s top scorer is out?`;
}
