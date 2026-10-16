"use client";

import { fetchConversation } from "@/lib/api/browser";
import { useResource } from "@/lib/api/use-resource";

import { useChatHistory } from "./ChatHistory";
import { ChatSession } from "./ChatSession";
import { ConversationNotFound, ConversationSkeleton } from "./ChatStates";

type ChatWorkspaceProps = {
  /** Set on `/chat/[id]`; a new chat has none. */
  conversationId: string | null;
  /** From `?fixture=`; ignored when a saved conversation already knows its fixture. */
  initialFixtureId: number | null;
};

/** Loads a saved conversation if there is one, then hands over to the live session. */
export function ChatWorkspace({ conversationId, initialFixtureId }: ChatWorkspaceProps) {
  const { sessionNonce } = useChatHistory();
  const conversation = useResource((signal) => fetchConversation(conversationId ?? "", signal), conversationId);

  if (conversationId === null) {
    return <ChatSession key={`new-${sessionNonce}`} conversationId={null} fixtureId={initialFixtureId} initialMessages={[]} />;
  }
  if (conversation.resource.status === "ready") {
    const { data } = conversation.resource;
    return <ChatSession key={`${data.id}-${sessionNonce}`} conversationId={data.id} fixtureId={data.fixture_id} initialMessages={data.messages} />;
  }
  if (conversation.resource.status === "error") return <ConversationNotFound />;
  return <ConversationSkeleton />;
}
