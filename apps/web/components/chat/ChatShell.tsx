"use client";

import type { ReactNode } from "react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

import { ChatHistoryProvider, useChatHistory } from "./ChatHistory";
import { HistoryList } from "./HistoryList";

/** The chat frame: a history sidebar beside the conversation, a slide-in sheet under 860px. */
export function ChatShell({ children }: { children: ReactNode }) {
  return (
    <ChatHistoryProvider>
      <Frame>{children}</Frame>
    </ChatHistoryProvider>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const { sheetOpen, setSheetOpen } = useChatHistory();
  return (
    <div className="flex h-[calc(100dvh-76px-var(--demo-bar-h,0px)-env(safe-area-inset-top,0px))] min-h-[520px] min-w-0 max-[860px]:min-h-0">
      <aside aria-label="Chat history" className="hidden w-[272px] shrink-0 overflow-y-auto border-r border-bp-border bg-bp-bg px-2.5 py-3.5 min-[860px]:block">
        <HistoryList />
      </aside>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-[min(300px,86%)] overflow-y-auto bg-bp-bg px-2.5 py-3.5">
          <SheetHeader className="p-0 pr-10">
            <SheetTitle>Chat history</SheetTitle>
            <SheetDescription className="sr-only">Your saved chats, newest first.</SheetDescription>
          </SheetHeader>
          <HistoryList />
        </SheetContent>
      </Sheet>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
