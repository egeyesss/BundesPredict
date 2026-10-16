"use client";

import { History } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ClubCrest } from "@/components/brand/ClubCrest";
import { KickoffTime } from "@/components/matchday/KickoffTime";
import { AgentOrb } from "@/components/signature/AgentOrb";
import { OddsBar } from "@/components/signature/OddsBar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { OrbState } from "@/lib/agent-state";
import type { FixtureDetail, Markets } from "@/lib/api/types";
import type { Resource } from "@/lib/api/use-resource";

type PinnedFixtureProps = {
  fixture: Resource<FixtureDetail>;
  /** The latest odds the agent produced for this match with the user's news applied. */
  news: Markets | null;
  orb: OrbState;
  onOpenHistory: () => void;
  /** The landmark name; only the styleguide shows two at once and needs to tell them apart. */
  label?: string;
};

const probsOf = (markets: Pick<Markets, "p_home" | "p_draw" | "p_away">) => [markets.p_home, markets.p_draw, markets.p_away] as const;
const goalsOf = (markets: Pick<Markets, "exp_home_goals" | "exp_away_goals">) => [markets.exp_home_goals, markets.exp_away_goals] as const;

/**
 * The match the conversation is about, with its odds. Plain "Model" odds until an answer applies
 * news; then the odds with that news, and a toggle back to the original.
 */
export function PinnedFixture({ fixture, news, orb, onOpenHistory, label = "Pinned fixture" }: PinnedFixtureProps) {
  const [showOriginal, setShowOriginal] = useState(false);

  return (
    <section
      aria-label={label}
      aria-busy={fixture.status === "loading"}
      className="grid gap-2.5 border-b border-bp-border bg-bp-bg px-5 py-3 max-[860px]:px-3.5"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-3 min-[521px]:flex-nowrap">
        <Button type="button" variant="secondary" size="sm" onClick={onOpenHistory} className="min-[860px]:hidden">
          <History /> History
        </Button>
        <FixtureTitle fixture={fixture} />
        <div className="ml-auto flex items-center gap-2.5 font-mono text-xs whitespace-nowrap text-bp-text-muted">
          {fixture.status === "ready" && (
            <span className="max-[520px]:hidden">
              <KickoffTime kickoffUtc={fixture.data.kickoff_utc} /> · MD {fixture.data.matchday}
            </span>
          )}
          <AgentOrb state={orb} size="chatHeader" />
        </div>
      </div>

      {fixture.status === "ready" && (
        <FixtureOdds fixture={fixture.data} news={news} showOriginal={showOriginal} onToggle={() => setShowOriginal((shown) => !shown)} />
      )}
    </section>
  );
}

function FixtureTitle({ fixture }: { fixture: Resource<FixtureDetail> }) {
  if (fixture.status === "ready") {
    const { home, away } = fixture.data;
    return (
      <div className="flex min-w-0 items-center gap-2.5 font-display text-[22px] leading-none font-bold tracking-[0.02em] max-[520px]:order-last max-[520px]:basis-full max-[520px]:text-[20px]">
        <ClubCrest team={home} size={32} />
        <span className="truncate">{home.short_name}</span>
        <span className="font-mono text-xs font-medium text-bp-text-muted">v</span>
        <span className="truncate">{away.short_name}</span>
        <ClubCrest team={away} size={32} />
      </div>
    );
  }
  if (fixture.status === "loading") {
    return (
      <div className="flex items-center gap-2.5">
        <Skeleton className="size-8 rounded-full" />
        <Skeleton className="h-5 w-40" />
        <Skeleton className="size-8 rounded-full" />
      </div>
    );
  }
  if (fixture.status === "error") {
    return <p className="text-sm text-bp-text-muted">Couldn&apos;t load this fixture</p>;
  }
  return (
    <p className="text-sm text-bp-text-muted">
      No fixture pinned.{" "}
      <Link href="/matchday" className="font-medium text-bp-text underline underline-offset-4">
        Pick a fixture
      </Link>
    </p>
  );
}

function FixtureOdds({
  fixture,
  news,
  showOriginal,
  onToggle,
}: {
  fixture: FixtureDetail;
  news: Markets | null;
  showOriginal: boolean;
  onToggle: () => void;
}) {
  const showingNews = news !== null && !showOriginal;
  const odds = showingNews ? news : fixture.base;
  const label = news === null ? "Model" : showingNews ? "With your news" : "Original model";

  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-center gap-x-3 gap-y-1 max-[520px]:grid-cols-[6.5rem_minmax(0,1fr)]">
      <div className="grid justify-items-start gap-1">
        <span className={`font-mono text-[11px] tracking-wider uppercase ${showingNews ? "text-bp-text" : "text-bp-text-muted"}`}>{label}</span>
        {news !== null && (
          <button type="button" onClick={onToggle} className="rounded-sm text-[11px] text-bp-text-muted underline underline-offset-2 hover:text-bp-text">
            {showingNews ? "Show original odds" : "Show odds with your news"}
          </button>
        )}
      </div>
      <OddsBar home={fixture.home.short_name} away={fixture.away.short_name} probs={probsOf(odds)} expectedGoals={goalsOf(odds)} />
    </div>
  );
}
