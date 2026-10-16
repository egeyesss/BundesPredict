"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { fetchConversations, fetchTeams, fetchWeekFixtures } from "@/lib/api/browser";
import type { ConversationSummary, FixtureCard, Team } from "@/lib/api/types";
import { useResource, type Resource } from "@/lib/api/use-resource";

type ChatHistoryValue = {
  conversations: Resource<ConversationSummary[]>;
  /** Adds or refreshes a chat started in this session without refetching the list. */
  upsert: (conversation: ConversationSummary) => void;
  reload: () => void;
  hasMore: boolean;
  loadingMore: boolean;
  loadMore: () => void;
  fixturesById: ReadonlyMap<number, FixtureCard>;
  teams: readonly Team[] | undefined;
  activeId: string | null;
  setActiveId: (id: string | null) => void;
  sheetOpen: boolean;
  setSheetOpen: (open: boolean) => void;
  /** Changes whenever "New chat" is chosen, so an open conversation view can start over. */
  sessionNonce: number;
  startNewChat: () => void;
};

const ChatHistoryContext = createContext<ChatHistoryValue | null>(null);

export function useChatHistory(): ChatHistoryValue {
  const value = useContext(ChatHistoryContext);
  if (value === null) throw new Error("useChatHistory must be used inside ChatHistoryProvider.");
  return value;
}

const byNewest = (a: ConversationSummary, b: ConversationSummary) => b.updated_at.localeCompare(a.updated_at);

function mergeById(...lists: ConversationSummary[][]): ConversationSummary[] {
  const merged = new Map<string, ConversationSummary>();
  for (const conversation of lists.flat()) merged.set(conversation.id, conversation);
  return [...merged.values()].toSorted(byNewest);
}

export function ChatHistoryProvider({ children }: { children: ReactNode }) {
  const firstPage = useResource((signal) => fetchConversations(signal), "conversations");
  const week = useResource(fetchWeekFixtures, "week-fixtures");
  const teams = useResource(fetchTeams, "teams");

  const [local, setLocal] = useState<ConversationSummary[]>([]);
  const [older, setOlder] = useState<{ items: ConversationSummary[]; next: string | null } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sessionNonce, setSessionNonce] = useState(0);

  const upsert = useCallback((conversation: ConversationSummary) => {
    setLocal((current) => [conversation, ...current.filter((item) => item.id !== conversation.id)]);
  }, []);

  const nextCursor = older ? older.next : firstPage.resource.status === "ready" ? firstPage.resource.data.next : null;

  const loadMore = useCallback(() => {
    if (nextCursor === null) return;
    setLoadingMore(true);
    fetchConversations(new AbortController().signal, nextCursor)
      .then((page) => setOlder((current) => ({ items: [...(current?.items ?? []), ...page.results], next: page.next })))
      .catch(() => toast.error("Couldn't load older chats. Check your connection."))
      .finally(() => setLoadingMore(false));
  }, [nextCursor]);

  const conversations: Resource<ConversationSummary[]> =
    firstPage.resource.status === "ready"
      ? { status: "ready", data: mergeById(firstPage.resource.data.results, older?.items ?? [], local) }
      : firstPage.resource.status === "error"
        ? firstPage.resource
        : { status: "loading" };

  const fixturesById = useMemo(
    () => new Map((week.resource.status === "ready" ? week.resource.data : []).map((fixture) => [fixture.id, fixture])),
    [week.resource],
  );

  const value: ChatHistoryValue = {
    conversations,
    upsert,
    reload: firstPage.reload,
    hasMore: nextCursor !== null,
    loadingMore,
    loadMore,
    fixturesById,
    teams: teams.resource.status === "ready" ? teams.resource.data : undefined,
    activeId,
    setActiveId,
    sheetOpen,
    setSheetOpen,
    sessionNonce,
    startNewChat: () => {
      setSessionNonce((nonce) => nonce + 1);
      setSheetOpen(false);
    },
  };

  return <ChatHistoryContext.Provider value={value}>{children}</ChatHistoryContext.Provider>;
}
