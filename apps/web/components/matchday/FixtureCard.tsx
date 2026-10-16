import Link from "next/link";

import { ClubCrest } from "@/components/brand/ClubCrest";
import { OddsBar } from "@/components/signature/OddsBar";
import type { FixtureCard as Fixture } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import "./matchday.css";
import { KickoffTime } from "./KickoffTime";

type FixtureCardProps = {
  fixture: Fixture;
  /** Delay before the one-time entry animation; leave unset to skip it. */
  enterDelayMs?: number;
  className?: string;
};

/** A scorebug: both clubs on one line, the 1X2 bar under them, expected goals and the way into the chat. */
export function FixtureCard({ fixture, enterDelayMs, className }: FixtureCardProps) {
  const { home, away, base } = fixture;
  const label = `${home.short_name} v ${away.short_name}`;

  return (
    <article
      aria-label={label}
      data-enter={enterDelayMs === undefined ? undefined : ""}
      style={enterDelayMs === undefined ? undefined : ({ "--enter-delay": `${enterDelayMs}ms` } as React.CSSProperties)}
      className={cn(
        "fixture-card grid min-w-0 gap-3 rounded-[var(--bp-radius)] border border-bp-border bg-bp-surface-1 px-4 py-3.5",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 font-mono text-xs text-bp-text-muted">
        <KickoffTime kickoffUtc={fixture.kickoff_utc} />
        <span aria-hidden="true">
          {home.code} v {away.code}
        </span>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2.5">
        <span className="flex min-w-0 items-center gap-2">
          <ClubCrest team={home} size={32} />
          <span className="truncate font-display text-[22px] leading-none font-bold tracking-[0.02em]">{home.short_name}</span>
        </span>
        <span aria-hidden="true" className="font-mono text-xs font-medium text-bp-text-muted">
          v
        </span>
        <span className="flex min-w-0 items-center justify-end gap-2">
          <span className="truncate font-display text-[22px] leading-none font-bold tracking-[0.02em]">{away.short_name}</span>
          <ClubCrest team={away} size={32} />
        </span>
      </div>

      <OddsBar
        home={home.short_name}
        away={away.short_name}
        probs={[base.p_home, base.p_draw, base.p_away]}
        expectedGoals={[base.exp_home_goals, base.exp_away_goals]}
      />

      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-mono text-bp-text-muted tabular-nums">
          xG <b className="font-semibold text-bp-text">{base.exp_home_goals.toFixed(2)}</b> {"–"}{" "}
          <b className="font-semibold text-bp-text">{base.exp_away_goals.toFixed(2)}</b>
        </span>
        <Link
          href={`/chat?fixture=${fixture.id}`}
          className="rounded-sm text-[13px] font-medium text-bp-text hover:text-bp-red-text"
        >
          Ask about this match →
        </Link>
      </div>
    </article>
  );
}
