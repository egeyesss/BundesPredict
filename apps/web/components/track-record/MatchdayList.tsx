import { ClubCrest } from "@/components/brand/ClubCrest";
import { OddsBar } from "@/components/signature/OddsBar";
import { cn } from "@/lib/utils";

import { formatDayRange, score, type MatchdayRow } from "./format";

type Fixture = MatchdayRow["fixtures"][number];

const OUTCOME_INDEX = { H: 0, D: 1, A: 2 } as const;

function codeOf(team: Fixture["home"]) {
  return team.code ?? team.name.slice(0, 3).toUpperCase();
}

function FixtureRow({ fixture }: { fixture: Fixture }) {
  const { home, away } = fixture;
  const actual = OUTCOME_INDEX[fixture.outcome];
  const probs = [fixture.p_home, fixture.p_draw, fixture.p_away] as const;
  const markerAt = probs.slice(0, actual).reduce((sum, p) => sum + p, 0) + probs[actual] / 2;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_56px] items-center gap-x-3.5 gap-y-2 border-t border-bp-border px-4 py-2.5 min-[720px]:grid-cols-[minmax(0,1.4fr)_64px_minmax(0,1.5fr)_132px]">
      <span className="flex min-w-0 items-center gap-2 font-display text-[17px] leading-tight font-semibold tracking-[0.02em]">
        <ClubCrest team={{ name: home.name, code: codeOf(home) }} size={20} />
        <span className="truncate">{home.name}</span>
        <span aria-hidden="true" className="font-mono text-xs font-normal text-bp-text-muted">
          v
        </span>
        <span className="truncate">{away.name}</span>
        <ClubCrest team={{ name: away.name, code: codeOf(away) }} size={20} />
      </span>
      <span className="text-center font-display text-xl leading-none font-bold tabular-nums" aria-label={`Final score ${fixture.home_goals} to ${fixture.away_goals}`}>
        {fixture.home_goals}–{fixture.away_goals}
      </span>
      <div className="relative col-span-full pt-1.5 min-[720px]:col-span-1">
        <OddsBar home={codeOf(home)} away={codeOf(away)} probs={probs} expectedGoals={[1, 1]} />
        <span aria-hidden="true" className="absolute top-[-2px] size-0 -translate-x-1/2 border-4 border-transparent border-t-bp-text" style={{ left: `${markerAt * 100}%` }} />
      </div>
      <span className="col-span-full font-mono text-xs text-bp-text-muted min-[720px]:col-span-1 min-[720px]:text-right">
        RPS {fixture.rps.toFixed(3)}
        <span className={cn("block text-[11px]", fixture.hit ? "text-bp-text" : "text-bp-text-muted")}>{fixture.hit ? "favourite won" : "favourite didn't win"}</span>
      </span>
    </li>
  );
}

/** Every scored match, newest matchday first, the latest one open. */
export function MatchdayList({ rows }: { rows: MatchdayRow[] }) {
  const scored = rows.filter((row) => row.n_resolved > 0);
  return (
    <div className="grid gap-2">
      {scored.map((row, index) => {
        const hits = Math.round((row.hit_rate ?? 0) * row.n_resolved);
        const kickoffs = row.fixtures.map((fixture) => fixture.kickoff_utc);
        return (
          <details key={`${row.season}-${row.matchday}`} open={index === 0} className="group rounded-[10px] border border-bp-border bg-bp-surface-1">
            <summary className="grid cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto_auto_18px] items-center gap-4 px-4 py-3.5 max-[560px]:grid-cols-[minmax(0,1fr)_auto_18px] [&::-webkit-details-marker]:hidden">
              <span className="font-display text-xl leading-none font-bold">
                Matchday {row.matchday}
                {kickoffs.length > 0 && <span className="ml-2.5 font-mono text-xs font-normal text-bp-text-muted">{formatDayRange(kickoffs[0], kickoffs[kickoffs.length - 1])}</span>}
              </span>
              <span className="font-mono text-xs whitespace-nowrap text-bp-text-muted max-[560px]:hidden">
                RPS <b className="font-medium text-bp-text">{row.rps === null ? "n/a" : score(row.rps)}</b>
              </span>
              <span className="font-mono text-xs whitespace-nowrap text-bp-text-muted">
                favourite won{" "}
                <b className="font-medium text-bp-text">
                  {hits}/{row.n_resolved}
                </b>
              </span>
              <span aria-hidden="true" className="font-mono text-bp-text-muted group-open:hidden">
                +
              </span>
              <span aria-hidden="true" className="hidden font-mono text-bp-text-muted group-open:inline">
                −
              </span>
            </summary>
            <ul>
              {row.fixtures.map((fixture) => (
                <FixtureRow key={fixture.fixture_id} fixture={fixture} />
              ))}
            </ul>
          </details>
        );
      })}
    </div>
  );
}
