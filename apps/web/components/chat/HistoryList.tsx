"use client";

import { MessageSquarePlus, RefreshCw, X } from "lucide-react";
import Link from "next/link";

import { ClubCrest } from "@/components/brand/ClubCrest";
import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { groupConversations } from "@/lib/chat/history";
import { cn } from "@/lib/utils";

import { useChatHistory } from "./ChatHistory";

/** The saved chats, grouped by when they were last used, with the way to start a new one. */
export function HistoryList() {
  const history = useChatHistory();
  const { conversations } = history;

  return (
    <div className="grid content-start gap-3.5">
      <Link
        href="/chat"
        onClick={history.startNewChat}
        className="inline-flex items-center gap-2 rounded-md border border-bp-border bg-bp-surface-2 px-3 py-2.5 text-sm font-medium hover:border-bp-text-muted/50"
      >
        <MessageSquarePlus className="size-4" aria-hidden="true" /> New chat
      </Link>

      {conversations.status === "loading" && <HistorySkeleton />}
      {conversations.status === "error" && <HistoryFailed status={conversations.failure.status} onRetry={history.reload} />}
      {conversations.status === "ready" && conversations.data.length === 0 && <HistoryEmpty />}
      {conversations.status === "ready" && <HistoryGroups />}
    </div>
  );
}

function HistoryGroups() {
  const history = useChatHistory();
  if (history.conversations.status !== "ready") return null;
  const groups = groupConversations(history.conversations.data, new Date());

  return (
    <>
      {groups.map((group) => (
        <section key={group.label} aria-label={group.label} className="grid gap-0.5">
          <h3 className="px-2 pb-1 font-mono text-[11px] font-medium tracking-[0.08em] text-bp-text-muted uppercase">{group.label}</h3>
          {group.items.map((conversation) => {
            const fixture = conversation.fixture_id === null ? undefined : history.fixturesById.get(conversation.fixture_id);
            const active = history.activeId === conversation.id;
            return (
              <Link
                key={conversation.id}
                href={`/chat/${conversation.id}`}
                aria-current={active ? "page" : undefined}
                onClick={() => history.setSheetOpen(false)}
                className={cn(
                  "grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2.5 rounded-lg p-2 text-bp-text-muted hover:bg-bp-surface-1 hover:text-bp-text",
                  active && "bg-bp-surface-2 text-bp-text",
                )}
              >
                <span aria-hidden="true" className="flex">
                  {fixture ? (
                    <>
                      <ClubCrest team={fixture.home} size={20} />
                      <ClubCrest team={fixture.away} size={20} className="-ml-1" />
                    </>
                  ) : (
                    <span className="size-5" />
                  )}
                </span>
                <span className="grid min-w-0">
                  <b className="truncate text-[13px] font-medium">{conversation.title}</b>
                  <span className="truncate text-xs text-bp-text-muted">
                    {fixture ? `${fixture.home.short_name} v ${fixture.away.short_name}` : "General question"}
                  </span>
                </span>
              </Link>
            );
          })}
        </section>
      ))}
      {history.hasMore && (
        <Button type="button" variant="ghost" size="sm" onClick={history.loadMore} disabled={history.loadingMore}>
          Show older chats
        </Button>
      )}
    </>
  );
}

export function HistoryEmpty() {
  return (
    <StateMessage
      as="h3"
      icon={<MessageSquarePlus className="size-4" />}
      title="No chats yet"
      actions={
        <Button asChild variant="secondary" size="sm">
          <Link href="/matchday">Go to matchday</Link>
        </Button>
      }
      className="px-1"
    >
      Pick a fixture on the matchday page and tell the agent what changed: a lineup, an injury, the weather.
    </StateMessage>
  );
}

export function HistorySkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading chats" className="grid gap-3 px-1">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="flex items-center gap-2.5">
          <Skeleton className="size-5 rounded-full" />
          <div className="grid flex-1 gap-1.5">
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-2.5 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function HistoryFailed({ status, onRetry }: { status: number; onRetry: () => void }) {
  if (status === 401) {
    return (
      <StateMessage
        as="h3"
        icon={<MessageSquarePlus className="size-4" />}
        title="Sign in to keep your chats"
        actions={
          <Button asChild size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
        }
        className="px-1"
      >
        Your conversations are saved to your account.
      </StateMessage>
    );
  }

  return (
    <StateMessage
      as="h3"
      tone="crit"
      icon={<X className="size-4" />}
      title="Couldn't load your chats"
      actions={
        <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      }
      className="px-1"
    >
      The connection to our server failed. Your chats are safe.
    </StateMessage>
  );
}
