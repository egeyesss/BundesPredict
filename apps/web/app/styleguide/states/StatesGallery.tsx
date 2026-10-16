"use client";

import type { ReactNode } from "react";

import { HistoryEmpty, HistoryFailed, HistorySkeleton } from "@/components/chat/HistoryList";
import { AssistantTurn } from "@/components/chat/AssistantTurn";
import { ConversationNotFound, ConversationSkeleton, SignInPrompt } from "@/components/chat/ChatStates";
import { Composer } from "@/components/chat/Composer";
import { LimitReached } from "@/components/chat/LimitReached";
import { PinnedFixture } from "@/components/chat/PinnedFixture";
import { QuotaMeter } from "@/components/chat/QuotaMeter";
import { MatchdayEmpty, MatchdayError, MatchdaySkeleton } from "@/components/matchday/MatchdayStates";
import { INITIAL_AGENT_STATE } from "@/lib/agent-state";
import { teams } from "@/lib/api/mocks/data";
import { ApiFailure } from "@/lib/api/use-resource";
import type { AssistantTurn as Turn } from "@/lib/chat/transcript";

import { Section } from "../Section";

const USAGE = { used: 3, limit: 3, resets_at: "2026-10-16T00:00:00Z" };
const NOOP = () => {};

function Specimen({ name, children }: { name: string; children: ReactNode }) {
  return (
    <figure data-specimen={name} className="grid min-w-0 content-start gap-3 rounded-xl border border-bp-border bg-bp-bg p-4">
      <figcaption className="font-mono text-xs text-bp-text-muted">{name}</figcaption>
      {children}
    </figure>
  );
}

function failedTurn(phase: Turn["phase"], error: string): Turn {
  return {
    kind: "assistant",
    id: phase,
    phase,
    agent: { ...INITIAL_AGENT_STATE, orb: { phase: "error", message: error } },
    text: phase === "cut_off" ? "Without Kane, Bayern's expected goals drop from 2.61 to 2.01. You described a long absence, so the agent asked for" : "",
    result: null,
    error,
    retryText: "Kane is out, how does that change Bayern v Leipzig?",
    animate: false,
  };
}

export function StatesGallery() {
  return (
    <>
      <Section id="matchday" title="Matchday" note="Skeletons are shaped like the real cards; errors say what broke and what to do.">
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          <Specimen name="fixtures.loading">
            <MatchdaySkeleton />
          </Specimen>
          <div className="grid content-start gap-4">
            <Specimen name="fixtures.empty">
              <MatchdayEmpty />
            </Specimen>
            <Specimen name="fixtures.error">
              <MatchdayError />
            </Specimen>
          </div>
        </div>
      </Section>

      <Section id="chat" title="Chat" note="Every way an answer can fail, and what the user sees.">
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          <Specimen name="conversation.loading">
            <ConversationSkeleton />
          </Specimen>
          <Specimen name="conversation.notFound">
            <ConversationNotFound />
          </Specimen>
          <Specimen name="history.loading">
            <HistorySkeleton />
          </Specimen>
          <Specimen name="history.empty">
            <HistoryEmpty />
          </Specimen>
          <Specimen name="history.error">
            <HistoryFailed status={500} onRetry={NOOP} />
          </Specimen>
          <Specimen name="history.signedOut">
            <HistoryFailed status={401} onRetry={NOOP} />
          </Specimen>
          <Specimen name="fixture.loading">
            <PinnedFixture fixture={{ status: "loading" }} news={null} orb={{ phase: "idle" }} onOpenHistory={NOOP} label="Pinned fixture while loading" />
          </Specimen>
          <Specimen name="fixture.error">
            <PinnedFixture
              fixture={{ status: "error", failure: new ApiFailure(404, "not_found", "Not found.") }}
              news={null}
              orb={{ phase: "idle" }}
              onOpenHistory={NOOP}
              label="Pinned fixture that failed to load"
            />
          </Specimen>
          <Specimen name="agent.model_unavailable">
            <AssistantTurn
              turn={failedTurn("failed", "The model isn't available right now. This chat wasn't counted. The model is usually back within a few minutes.")}
              teams={teams}
              onWritten={NOOP}
              onRetry={NOOP}
            />
          </Specimen>
          <Specimen name="stream.cut_off">
            <AssistantTurn turn={failedTurn("cut_off", "The answer was cut off by a lost connection.")} teams={teams} onWritten={NOOP} onRetry={NOOP} />
          </Specimen>
          <Specimen name="agent.rate_limited">
            <Composer
              value="Kane is out"
              onChange={NOOP}
              onSend={NOOP}
              busy={false}
              placeholder="Tell the agent what changed"
              rateLimit={{ active: true, finished: false, secondsLeft: 24 }}
              meter={<QuotaMeter plan="free" usage={{ ...USAGE, used: 1 }} />}
            />
          </Specimen>
          <Specimen name="quota.exhausted">
            <LimitReached plan="free" usage={USAGE} />
          </Specimen>
          <Specimen name="demo.exhausted">
            <LimitReached plan="demo" usage={{ ...USAGE, used: 10, limit: 10 }} />
          </Specimen>
          <Specimen name="auth.required">
            <SignInPrompt />
          </Specimen>
        </div>
      </Section>
    </>
  );
}
