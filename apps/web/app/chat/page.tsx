import type { Metadata } from "next";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

export const metadata: Metadata = { title: "Chat" };

export default async function ChatPage({ searchParams }: { searchParams: Promise<{ fixture?: string }> }) {
  const { fixture } = await searchParams;
  const fixtureId = /^\d{1,9}$/.test(fixture ?? "") ? Number(fixture) : null;
  return <ChatWorkspace conversationId={null} initialFixtureId={fixtureId} />;
}
