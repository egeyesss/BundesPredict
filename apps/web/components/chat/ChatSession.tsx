"use client";

import { useEffect, useReducer, useRef, useState } from "react";

import { useIslandActivity } from "@/components/brand/IslandActivity";
import { captionFor, type AgentEvent } from "@/lib/agent-state";
import { browserOrigin, fetchFixture, fetchMe } from "@/lib/api/browser";
import { startPredictStream, type PredictStreamStart } from "@/lib/api/predict-stream";
import type { Message, PredictStreamEvent, QuotaExceededError, Usage } from "@/lib/api/types";
import { useResource } from "@/lib/api/use-resource";
import { isExhausted } from "@/lib/chat/quota";
import { resultMatchesFixture } from "@/lib/chat/teams";
import { INITIAL_TRANSCRIPT, isBusy, latestResult, transcriptReducer, type AssistantTurn as Assistant } from "@/lib/chat/transcript";
import { Skeleton } from "@/components/ui/skeleton";
import { DONE_HOLD_MS } from "@/lib/agent-state";

import { AssistantTurn } from "./AssistantTurn";
import { useChatHistory } from "./ChatHistory";
import { EmptyChat, SignInPrompt } from "./ChatStates";
import { Composer } from "./Composer";
import { LimitReached } from "./LimitReached";
import { PinnedFixture } from "./PinnedFixture";
import { QuotaMeter } from "./QuotaMeter";
import { useCountdown } from "./use-countdown";
import { useNarrowScreen } from "./use-narrow-screen";
import { useStickToBottom } from "./use-stick-to-bottom";
import { UserTurn } from "./UserTurn";

const DEFAULT_RETRY_SECONDS = 30;

const MESSAGES = {
  unavailable: "The model isn't available right now. This chat wasn't counted. The model is usually back within a few minutes.",
  unreachable: "We couldn't reach the agent. This chat wasn't counted. Check your connection and try again.",
  cutOff: "The answer was cut off by a lost connection.",
} as const;

type ChatSessionProps = {
  conversationId: string | null;
  fixtureId: number | null;
  initialMessages: readonly Message[];
};

export function ChatSession({ conversationId, fixtureId, initialMessages }: ChatSessionProps) {
  const history = useChatHistory();
  const { setAgentCaption } = useIslandActivity();
  const [transcript, dispatch] = useReducer(transcriptReducer, initialMessages, (messages) =>
    transcriptReducer(INITIAL_TRANSCRIPT, { type: "load", messages }),
  );
  const [draft, setDraft] = useState("");
  const [usageOverride, setUsageOverride] = useState<Usage | null>(null);
  const [needsSignIn, setNeedsSignIn] = useState(false);
  const rateLimit = useCountdown();

  const me = useResource(fetchMe, "me");
  const fixture = useResource((signal) => fetchFixture(fixtureId ?? 0, signal), fixtureId === null ? null : `fixture-${fixtureId}`);

  const activeConversation = useRef<string | null>(conversationId);
  const turnCount = useRef(0);
  const run = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  useStickToBottom(logRef, contentRef);

  const busy = isBusy(transcript);
  const lastAssistant = transcript.findLast((turn): turn is Assistant => turn.kind === "assistant");
  const orb = lastAssistant?.agent.orb ?? { phase: "idle" as const };

  useEffect(() => {
    history.setActiveId(conversationId);
    return () => history.setActiveId(null);
    // `history` changes identity every render; only the conversation decides the highlight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, history.setActiveId]);

  const caption = captionFor(orb);
  useEffect(() => {
    setAgentCaption(busy ? caption : null);
    return () => setAgentCaption(null);
  }, [busy, caption, setAgentCaption]);

  useEffect(() => () => run.current?.abort(), []);

  useEffect(() => {
    if (orb.phase !== "done") return;
    const timer = setTimeout(() => dispatch({ type: "agent", event: { event: "settle" } }), DONE_HOLD_MS);
    return () => clearTimeout(timer);
  }, [orb.phase]);

  function handleStreamEvent(event: PredictStreamEvent) {
    dispatch({ type: "agent", event: event as AgentEvent });
    if (event.event === "quota") setUsageOverride(event.data);
    if (event.event === "conversation" && event.data.id !== null) {
      activeConversation.current = event.data.id;
      history.setActiveId(event.data.id);
      history.upsert({ id: event.data.id, title: event.data.title, fixture_id: fixtureId, updated_at: new Date().toISOString() });
    }
  }

  function handleRejected(outcome: Extract<PredictStreamStart, { ok: false }>, query: string) {
    switch (outcome.status) {
      case 402:
        setUsageOverride((outcome.error as QuotaExceededError).usage);
        dispatch({ type: "discard" });
        return;
      case 401:
        setNeedsSignIn(true);
        dispatch({ type: "discard" });
        return;
      case 429:
        rateLimit.start(outcome.retryAfterSeconds ?? DEFAULT_RETRY_SECONDS);
        setDraft(query);
        dispatch({ type: "discard" });
        return;
      case 503:
        dispatch({ type: "reject", message: MESSAGES.unavailable });
        return;
      case 400:
        dispatch({ type: "reject", message: outcome.error.message });
        return;
      default:
        dispatch({ type: "reject", message: MESSAGES.unreachable });
    }
  }

  async function send(text: string) {
    const query = text.trim();
    if (query === "" || busy) return;

    turnCount.current += 1;
    dispatch({ type: "send", id: `turn-${turnCount.current}`, text: query });
    setDraft("");

    const controller = new AbortController();
    run.current = controller;

    let started: PredictStreamStart;
    try {
      started = await startPredictStream(
        { query, conversation_id: activeConversation.current, fixture_id: fixtureId },
        { baseUrl: browserOrigin(), signal: controller.signal },
      );
    } catch {
      if (!controller.signal.aborted) dispatch({ type: "reject", message: MESSAGES.unreachable });
      return;
    }
    if (!started.ok) return handleRejected(started, query);

    let finished = false;
    try {
      for await (const event of started.events) {
        handleStreamEvent(event);
        if (event.event === "result" || event.event === "error") finished = true;
      }
    } catch {
      if (controller.signal.aborted) return;
    }
    if (!finished && !controller.signal.aborted) dispatch({ type: "cut", message: MESSAGES.cutOff });
  }

  function retry(text: string) {
    dispatch({ type: "discard" });
    void send(text);
  }

  const result = latestResult(transcript);
  const news =
    result?.adjusted && result.adjustments.length > 0 && fixture.resource.status === "ready" && resultMatchesFixture(result, fixture.resource.data)
      ? result.adjusted
      : null;

  const usage = usageOverride ?? (me.resource.status === "ready" ? me.resource.data.usage : null);
  const plan = me.resource.status === "ready" ? me.resource.data.plan : "free";
  const signInRequired = needsSignIn || (me.resource.status === "error" && me.resource.failure.status === 401);
  const narrow = useNarrowScreen();
  const matchName = fixture.resource.status === "ready" ? `${fixture.resource.data.home.short_name} v ${fixture.resource.data.away.short_name}` : null;
  const placeholder = !matchName ? "Ask about a Bundesliga match" : narrow ? "Tell the agent what changed" : `Tell the agent what changed for ${matchName}`;

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_auto]">
      <h1 className="sr-only">{matchName ? `Chat about ${matchName}` : "Chat"}</h1>
      <PinnedFixture fixture={fixture.resource} news={news} orb={orb} onOpenHistory={() => history.setSheetOpen(true)} />

      <div ref={logRef} role="log" aria-label="Conversation" className="flex flex-col overflow-y-auto px-5 py-5 max-[860px]:px-3.5">
        <div ref={contentRef} className="flex flex-col gap-[22px]">
          {transcript.length === 0 && <EmptyChat match={matchName} />}
          {transcript.map((turn) =>
            turn.kind === "user" ? (
              <UserTurn key={turn.id} turn={turn} />
            ) : (
              <AssistantTurn key={turn.id} turn={turn} teams={history.teams} onWritten={() => dispatch({ type: "written" })} onRetry={retry} />
            ),
          )}
        </div>
      </div>

      <div className="border-t border-bp-border bg-bp-bg px-5 pt-3 pb-[calc(14px+env(safe-area-inset-bottom,0px))] max-[860px]:px-3.5">
        {signInRequired ? (
          <SignInPrompt />
        ) : usage !== null && isExhausted(plan, usage) && !busy ? (
          <div className="mx-auto w-full max-w-[760px]">
            <LimitReached plan={plan} usage={usage} timeZone={me.resource.status === "ready" ? (me.resource.data.timezone ?? undefined) : undefined} />
          </div>
        ) : (
          <Composer
            value={draft}
            onChange={setDraft}
            onSend={() => void send(draft)}
            busy={busy}
            placeholder={placeholder}
            rateLimit={{ active: rateLimit.active, finished: rateLimit.finished, secondsLeft: rateLimit.secondsLeft }}
            meter={usage ? <QuotaMeter plan={plan} usage={usage} /> : <Skeleton className="h-3 w-44" />}
          />
        )}
      </div>
    </div>
  );
}
