import Link from "next/link";

import { LeagueMark } from "@/components/brand/LeagueMark";
import type { FixtureScope, FixturesOutcome } from "@/lib/api/server";
import { groupByMatchday, seasonLabel } from "@/lib/matchday";
import { cn } from "@/lib/utils";

import { FixtureGrid } from "./FixtureGrid";
import { MatchdayEmpty, MatchdayError } from "./MatchdayStates";

const SCOPES: ReadonlyArray<{ scope: FixtureScope; label: string; href: string }> = [
  { scope: "next_matchday", label: "Next matchday", href: "/matchday" },
  { scope: "week", label: "This week", href: "/matchday?scope=week" },
];

function headline(outcome: FixturesOutcome): { title: string; detail: string | null } {
  if (outcome.status !== "ok" || outcome.fixtures.length === 0) return { title: "Bundesliga", detail: null };
  const groups = groupByMatchday(outcome.fixtures);
  const title = `Bundesliga ${seasonLabel(outcome.fixtures[0].season)}`;
  return { title, detail: groups.length === 1 ? `Matchday ${groups[0].matchday}` : "This week" };
}

export function MatchdayView({ outcome, scope }: { outcome: FixturesOutcome; scope: FixtureScope }) {
  const groups = outcome.status === "ok" ? groupByMatchday(outcome.fixtures) : [];
  const { title, detail } = headline(outcome);

  return (
    <div className="mx-auto grid w-full max-w-[1120px] gap-5 px-[max(16px,env(safe-area-inset-left))] pt-6 pb-12">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <LeagueMark placement="matchday-header" size={24} />
        <h1 className="font-display text-[clamp(24px,4vw,34px)] leading-none font-bold tracking-[0.02em] uppercase">
          {title}
          {detail && <span className="font-medium text-bp-text-muted"> · {detail}</span>}
        </h1>
        <nav aria-label="Fixture range" className="ml-auto inline-flex gap-0.5 rounded-full border border-bp-border bg-bp-bg p-[3px]">
          {SCOPES.map((option) => (
            <Link
              key={option.scope}
              href={option.href}
              aria-current={option.scope === scope ? "page" : undefined}
              className={cn(
                "rounded-full px-3 py-1.5 text-[13px] whitespace-nowrap text-bp-text-muted hover:text-bp-text",
                option.scope === scope && "bg-bp-text font-semibold text-bp-bg hover:text-bp-bg",
              )}
            >
              {option.label}
            </Link>
          ))}
        </nav>
      </header>

      {outcome.status === "error" && <MatchdayError />}
      {outcome.status === "ok" && groups.length === 0 && <MatchdayEmpty />}
      {groups.length === 1 && <FixtureGrid fixtures={groups[0].fixtures} label="Fixtures" />}
      {groups.length > 1 &&
        groups.map((group) => (
          <section key={group.matchday} aria-labelledby={`md-${group.matchday}`} className="grid gap-3">
            <h2 id={`md-${group.matchday}`} className="font-display text-xl font-semibold tracking-[0.04em] text-bp-text-muted uppercase">
              Matchday {group.matchday}
            </h2>
            <FixtureGrid fixtures={group.fixtures} label={`Matchday ${group.matchday} fixtures`} />
          </section>
        ))}
    </div>
  );
}
