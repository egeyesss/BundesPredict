import { ClubCrest } from "@/components/brand/ClubCrest";
import { cn } from "@/lib/utils";

import { beforeKickoff, edgeAxisLimit, newsOutcomeName, percent, points, type NewsChat, type NewsEdge as NewsEdgeData } from "./format";

const codeOf = (team: NewsChat["home"]) => team.code ?? team.name.slice(0, 3).toUpperCase();

function Dumbbell({ chat, limit }: { chat: NewsChat; limit: number }) {
  const at = (value: number) => `${((points(chat.opening ?? value, value) + limit) / (2 * limit)) * 100}%`;
  return (
    <div className="relative h-[30px]" aria-hidden="true">
      {[-0.5, 0.5].map((fraction) => (
        <i key={fraction} className="absolute top-1 bottom-1 w-px bg-[var(--chart-grid)]" style={{ left: `${50 + fraction * 100}%` }} />
      ))}
      <i className="absolute top-1 bottom-1 w-0.5 -translate-x-px bg-[var(--chart-faint)]" style={{ left: "50%" }} />
      {chat.closing !== null && chat.opening !== null && (
        <>
          <i className="absolute top-[14px] h-[3px] rounded-sm bg-[var(--series-market)]/45" style={{ left: `min(50%, ${at(chat.closing)})`, width: `${Math.abs(points(chat.opening, chat.closing)) / (2 * limit) * 100}%` }} />
          <i
            className="absolute top-[7px] size-4 -translate-x-1/2 rounded-full border-2 border-[var(--series-market)] bg-bp-surface-1"
            style={{ left: at(chat.closing) }}
          />
          <i
            className="absolute top-[10px] size-2.5 -translate-x-1/2 rounded-full bg-[var(--series-model)] shadow-[0_0_0_2px_var(--bp-surface-1)]"
            style={{ left: at(chat.agent) }}
          />
        </>
      )}
    </div>
  );
}

function Row({ chat, limit }: { chat: NewsChat; limit: number }) {
  const judged = chat.ahead !== null;
  const summary = judged
    ? `${newsOutcomeName(chat)}: opening ${percent(chat.opening!)}, agent ${percent(chat.agent)}, closing ${percent(chat.closing!)}, ${chat.verdict}`
    : `${newsOutcomeName(chat)}: agent ${percent(chat.agent)}, ${chat.verdict}`;
  return (
    <li aria-label={summary} className="grid grid-cols-[minmax(0,1.25fr)_minmax(0,1.6fr)_210px] items-center gap-4 border-b border-bp-border py-3 last:border-b-0 max-[860px]:grid-cols-1 max-[860px]:gap-2">
      <div className="grid min-w-0 gap-0.5">
        <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 font-display text-base leading-tight font-semibold tracking-[0.02em]">
          <span className="mr-1 shrink-0 font-mono text-[11px] font-normal whitespace-nowrap text-bp-text-muted">MD {chat.matchday}</span>
          <ClubCrest team={{ name: chat.home.name, code: codeOf(chat.home) }} size={20} />
          <span>{chat.home.name}</span>
          <span aria-hidden="true" className="font-mono text-xs font-normal text-bp-text-muted">v</span>
          <span>{chat.away.name}</span>
          <ClubCrest team={{ name: chat.away.name, code: codeOf(chat.away) }} size={20} />
        </span>
        <span className="font-mono text-[11px] text-bp-text-muted">
          {newsOutcomeName(chat)} · {beforeKickoff(chat.hours_before_kickoff)}
        </span>
      </div>
      {judged ? (
        <Dumbbell chat={chat} limit={limit} />
      ) : (
        <span className="font-mono text-xs text-bp-text-muted">Agent put it at {percent(chat.agent)}</span>
      )}
      <span className={cn("flex items-center gap-2 font-mono text-xs", chat.ahead ? "text-bp-text" : "text-bp-text-muted")}>
        <span
          aria-hidden="true"
          className={cn("grid size-[26px] shrink-0 place-items-center rounded-full text-xs font-bold", chat.ahead ? "bg-odds-win text-bp-bg" : "border border-bp-border")}
        >
          {chat.ahead ? "✓" : "–"}
        </span>
        {chat.verdict}
      </span>
    </li>
  );
}

function Key() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[13px] text-bp-text-muted">
      <span className="inline-flex items-center gap-1.5">
        <i className="h-3 w-0.5 bg-[var(--chart-faint)]" />
        Opening line (0)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <i className="size-3 rounded-full border-2 border-[var(--series-market)]" />
        Closing line
      </span>
      <span className="inline-flex items-center gap-1.5">
        <i className="size-2.5 rounded-full bg-[var(--series-model)]" />
        Agent, with your news
      </span>
      <span className="inline-flex items-center gap-1.5">
        <i className="grid size-4 place-items-center rounded-full bg-odds-win text-[10px] font-bold text-bp-bg not-italic">✓</i>
        Ahead of the market
      </span>
    </div>
  );
}

function Headline({ edge }: { edge: NewsEdgeData }) {
  if (edge.rate !== null) {
    return (
      <span className="w-fit rounded-lg border border-bp-border px-2 py-0.5 font-mono text-[11px] text-bp-text-muted">
        Ahead of the market in {edge.n_ahead} of {edge.n_compared} compared chats ({percent(edge.rate)})
      </span>
    );
  }
  const left = Math.max(0, edge.minimum_for_rate - edge.n_compared);
  return (
    <span className="w-fit max-w-full rounded-lg border border-bp-border px-2 py-0.5 font-mono text-[11px] leading-normal text-bp-text-muted">
      {edge.n_logged} {edge.n_logged === 1 ? "chat" : "chats"} logged, {edge.n_compared} compared. No rate until {edge.minimum_for_rate} are compared ({left} to go).
    </span>
  );
}

export function NewsEdge({ edge }: { edge: NewsEdgeData }) {
  const limit = edgeAxisLimit(edge.chats);
  return (
    <>
      <section aria-label="Where you come in" className="grid grid-cols-2 items-start gap-7 rounded-xl border border-bp-border bg-[radial-gradient(120%_140%_at_0%_0%,rgb(34_197_94/0.10),transparent_55%)] bg-bp-surface-1 p-7 max-[860px]:grid-cols-1 max-[860px]:p-5">
        <div className="grid gap-3 text-base text-[#D4D4D8] [&_strong]:font-semibold [&_strong]:text-bp-text">
          <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">Where you come in</span>
          <h2 className="font-display text-[clamp(30px,4.2vw,44px)] leading-none font-bold text-balance">
            The model alone doesn&apos;t beat the bookmakers. <em className="text-odds-win-text not-italic">Your news might.</em>
          </h2>
          <p>By kickoff, the closing line has priced in everything public, including news our goals-only model never sees. That is why the model on its own sits just behind it.</p>
          <p>
            <strong>The window is before the odds settle.</strong> Lines open early in the week and keep moving until kickoff. Bring the agent a lineup, an injury or a forecast before the market has caught up, and it reprices the match in seconds.
          </p>
          <p>We check every one of those chats against where the market actually finished, so you can see when the news put you ahead.</p>
        </div>
        <ol className="grid gap-2.5" aria-label="Timeline">
          {[
            ["Mon", "Bookmakers open their lines.", false],
            ["Sat 13:30", "Lineups drop. You tell the agent; it reprices in seconds.", true],
            ["Sat 15:30", "Kickoff. The closing line has finished moving.", false],
            ["Next day", "We compare your chat with both lines and log the result below.", false],
          ].map(([when, what, you]) => (
            <li key={String(when)} className="grid grid-cols-[74px_minmax(0,1fr)] items-baseline gap-3 border-b border-bp-border py-2.5 last:border-b-0">
              <b className={cn("font-mono text-xs font-semibold", you ? "text-odds-win-text" : "text-bp-text-muted")}>{when}</b>
              <span className="text-sm text-[#D4D4D8]">{what}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="News edge tracker" data-tour="edge" className="grid min-w-0 gap-3.5 rounded-xl border border-bp-border bg-bp-surface-1 p-5">
        <div className="grid gap-1">
          <h2 className="font-display text-xl leading-tight font-semibold tracking-[0.02em]">News edge tracker</h2>
          <p className="max-w-[70ch] text-sm text-bp-text-muted">
            Each row is a chat that brought news before kickoff. Points are the change from the opening line for the outcome the news moved most. A green circle means the agent&apos;s odds landed closer to the closing line than the opening line did, in the direction the market later moved. This is a separate measure from the model&apos;s score above, and chats stay private: only the odds are shown.
          </p>
        </div>
        <Headline edge={edge} />
        {edge.n_logged === 0 ? (
          <div className="grid gap-2 rounded-xl border border-dashed border-[#3a3a42] p-6">
            <h3 className="font-display text-xl font-semibold">No chats logged yet this season</h3>
            <p className="max-w-[70ch] text-sm text-bp-text-muted">
              Every chat that brings news before kickoff is logged with the odds the agent produced. After the match, it is checked against the opening and closing lines and shows up here, hits and misses alike.
            </p>
          </div>
        ) : (
          <>
            <Key />
            <ul>
              {edge.chats.map((chat) => (
                <Row key={chat.prediction_id} chat={chat} limit={limit} />
              ))}
            </ul>
          </>
        )}
      </section>
    </>
  );
}
