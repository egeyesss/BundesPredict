import { LogIn, MessageSquareOff } from "lucide-react";
import Link from "next/link";

import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** Shaped like a question and a finished answer, so the page does not jump when the chat arrives. */
export function ConversationSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading chat" className="mx-auto grid w-full max-w-[760px] gap-5 px-5 py-5">
      <Skeleton className="h-[34px] w-3/5 justify-self-end rounded-xl" />
      <div className="flex items-start gap-3">
        <Skeleton className="size-9 shrink-0 rounded-full" />
        <div className="grid flex-1 gap-2">
          <Skeleton className="h-2.5 w-[90%]" />
          <Skeleton className="h-2.5 w-[70%]" />
          <Skeleton className="h-2.5 w-1/2" />
        </div>
      </div>
      <Skeleton className="h-[86px] rounded-[var(--bp-radius)]" />
    </div>
  );
}

export function ConversationNotFound() {
  return (
    <div className="mx-auto w-full max-w-[760px] px-5 py-8">
      <StateMessage
        icon={<MessageSquareOff className="size-4" />}
        title="We couldn't find that chat"
        actions={
          <Button asChild variant="secondary">
            <Link href="/chat">Start a new chat</Link>
          </Button>
        }
      >
        It may have been deleted, or it belongs to another account.
      </StateMessage>
    </div>
  );
}

export function SignInPrompt() {
  return (
    <div role="status" className="mx-auto grid w-full max-w-[760px] gap-2.5 rounded-[var(--bp-radius)] border border-bp-border bg-bp-surface-1 px-4 py-3.5">
      <p className="m-0 text-sm text-bp-text-muted">
        <strong className="font-semibold text-bp-text">Sign in to ask the agent.</strong> Chats run on your account so your history and daily
        count follow you. Matchday odds stay open to everyone.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link href="/login">
            <LogIn /> Sign in
          </Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href="/matchday">Back to matchday</Link>
        </Button>
      </div>
    </div>
  );
}

export function EmptyChat({ match }: { match: string | null }) {
  return (
    <div className="m-auto grid max-w-[46ch] justify-items-center gap-2 py-10 text-center">
      <h2 className="font-display text-[26px] leading-tight font-semibold tracking-[0.02em]">
        {match ? `Ask about ${match}` : "Ask about a Bundesliga match"}
      </h2>
      <p className="text-sm text-bp-text-muted">
        Tell the agent what the model does not know yet: a lineup, an injury, the weather. It reruns the model with that news and shows how the odds move.
      </p>
    </div>
  );
}
