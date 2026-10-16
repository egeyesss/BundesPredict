import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { requireMe } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Chat" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!UUID.test(id)) notFound();
  await requireMe(`/chat/${id}`);
  return <ChatWorkspace conversationId={id} initialFixtureId={null} />;
}
