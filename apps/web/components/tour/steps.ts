import { NET_REVENUE_CENTS } from "@/components/admin/CostChart";
import { formatMoney } from "@/lib/admin/format";

export type TourScreen = "matchday" | "chat" | "record" | "admin";
export type TourSide = "top" | "bottom" | "left" | "right";

export type TourStep = {
  id: string;
  screen: TourScreen;
  /** `data-tour` names in order of preference; the first one that is on the page is the spotlight. */
  anchors: readonly string[];
  side: TourSide;
  title: string;
  what: string;
  how: string;
  /** Track record tab to open before the anchor is looked for. */
  tab?: "live" | "backtest";
  /** No "?" hotspot: the anchor lives inside the nav island, which sits above the hotspot layer. */
  hotspot?: false;
};

export const SCREEN_LABEL: Record<TourScreen, string> = {
  matchday: "Matchday",
  chat: "Chat",
  record: "Track record",
  admin: "Admin",
};

export const SCREEN_PATH: Record<TourScreen, string> = {
  matchday: "/matchday",
  chat: "/chat",
  record: "/track-record",
  admin: "/admin",
};

const NET_REVENUE = formatMoney(NET_REVENUE_CENTS);

export const STEPS: readonly TourStep[] = [
  {
    id: "fixture",
    screen: "matchday",
    anchors: ["fixture"],
    side: "right",
    title: "One card per fixture",
    what: "Every match of the next Bundesliga matchday, with kickoff shown in your own time zone.",
    how: "The schedule comes from OpenLigaDB and is refreshed every day at 05:00 UTC, together with the model.",
  },
  {
    id: "odds",
    screen: "matchday",
    anchors: ["bar"],
    side: "bottom",
    title: "Win, draw, loss odds",
    what: "Green marks the more likely team, red the less likely one and grey the draw. Only the leading outcome is in full colour.",
    how: "A Dixon-Coles model rates every team's attack and defence from the Bundesliga results in its database, going back to the 2020/21 season, and counts recent matches more. It turns those ratings into a full scoreline grid, so the three numbers always add up to 100.",
  },
  {
    id: "xg",
    screen: "matchday",
    anchors: ["xg"],
    side: "bottom",
    title: "Expected goals",
    what: "How many goals the model expects each side to score. Every probability on the site is built from these two numbers.",
    how: "A side's attack strength times the opponent's defence times the home advantage. The model is refit every day at 05:00 UTC on every result played before that day.",
  },
  {
    id: "ask",
    screen: "matchday",
    anchors: ["ask"],
    side: "left",
    title: "Bring the news",
    what: "When something changes that the model can't know, such as a lineup, an injury or the weather, ask the agent about the match.",
    how: "The chat opens pinned to this fixture, so the agent already knows which match you mean.",
  },
  {
    id: "message",
    screen: "chat",
    anchors: ["message", "composer"],
    side: "top",
    title: "Say what changed",
    what: "Plain words are fine. The agent works out which teams and players you mean. We filled in a hypothetical for this match; edit it or send it as it is.",
    how: "The agent looks players up in squad data scraped from Transfermarkt instead of trusting the name in your message. Sending uses one of your 10 demo chats.",
  },
  {
    id: "steps",
    screen: "chat",
    anchors: ["steps"],
    side: "right",
    title: "The agent shows its work",
    what: "Each line is one tool the agent called, such as the model, a squad lookup or the weather forecast, and what came back.",
    how: "The steps stream in while the agent works. Every answer is saved with your question, the adjustments it applied and what it cost to produce.",
  },
  {
    id: "result",
    screen: "chat",
    anchors: ["result"],
    side: "top",
    title: "Before and after",
    what: "The top bar is the model alone. The bottom bar is the same model after your news, and the gap is what the news is worth. If the news changes nothing, only the model's bar shows.",
    how: "Both bars come from the same scoreline grid. The agent can only move expected goals; the model recomputes every probability from scratch.",
  },
  {
    id: "chips",
    screen: "chat",
    anchors: ["chips", "result"],
    side: "top",
    title: "Capped adjustments",
    what: "Each chip is one nudge to expected goals: what the agent asked for and what it was allowed. Hover or focus a chip to read the agent's reason. No chips means the agent found nothing to adjust.",
    how: "Every adjustment is clamped to 0.60 xG either way on the server, whatever the language model asks for, and a chip says \"capped\" when a request went past that. There is no way for the agent to set a probability directly.",
  },
  {
    id: "quota",
    screen: "chat",
    anchors: ["quota"],
    side: "top",
    title: "Fair limits",
    what: "Free accounts get 3 chats a day and Pro gets 100. This demo account gets 10 in total for the 24 hours it lives.",
    how: "Each chat is counted in a single database statement, so two tabs can't sneak past the limit. A chat that fails before the agent runs is given back.",
  },
  {
    id: "upgrade",
    screen: "chat",
    anchors: ["upgrade"],
    side: "bottom",
    hotspot: false,
    title: "Try the real checkout",
    what: "Upgrading opens Stripe's checkout in test mode. Use card 4242 4242 4242 4242 with any future date and any CVC. Nothing is charged.",
    how: "Pro only switches on when Stripe's signed webhook reaches the server, never just because the browser came back from checkout. This demo stays capped at 10 chats in total even after an upgrade.",
  },
  {
    id: "rps",
    screen: "record",
    anchors: ["rps"],
    side: "bottom",
    tab: "backtest",
    title: "How accurate is it?",
    what: "Ranked probability score: 0 is perfect and lower is better. The model sits a little behind the bookmakers' closing line, and this page says so.",
    how: "The backtest predicted every match walk-forward: the model is refit before each gameweek using only earlier results, so nothing from the future leaks in.",
  },
  {
    id: "edge",
    screen: "record",
    anchors: ["edge"],
    side: "top",
    tab: "live",
    title: "The news edge",
    what: "Each row is a chat that brought news before kickoff. A green check means the agent moved the way the market later did and ended up nearer the closing line than the opening line was. This list can be empty or short right now.",
    how: "After the match, each chat sent within 7 days of kickoff is compared with the opening and closing odds. No rate is shown until 20 chats have been compared, and chats from demo accounts are left out.",
  },
  {
    id: "mrr",
    screen: "admin",
    anchors: ["mrr"],
    side: "bottom",
    title: "It runs as a business",
    what: "Monthly recurring revenue from paying subscribers. This demo view masks emails and nothing on the page can be changed.",
    how: "Only live-mode Stripe subscriptions count, synced from Stripe's webhooks. Test-mode checkouts like yours show up in the separate test-mode card.",
  },
  {
    id: "cost",
    screen: "admin",
    anchors: ["cost"],
    side: "top",
    title: "Does $5 cover the AI?",
    what: `What the heaviest Pro subscribers cost in agent usage over the last 30 days, against the ${NET_REVENUE} each one pays after Stripe's fee. The chart is empty until a Pro user has used the agent.`,
    how: "Token counts are logged on every prediction and priced per model, so each cost is worked out from real usage.",
  },
  {
    id: "webhooks",
    screen: "admin",
    anchors: ["webhooks"],
    side: "top",
    title: "Payments that can't double-count",
    what: "Every Stripe event the server received, with its status. A failed event drops off the list once Stripe's redelivery goes through.",
    how: "Each event id is stored once, so an event delivered twice is processed once. The handler re-reads the subscription from Stripe instead of trusting the order events arrive in.",
  },
];

/** The stops whose page is `pathname`; `/chat/<id>` counts as the chat screen. */
export function stepsOnPath(pathname: string): TourStep[] {
  return STEPS.filter((step) => {
    const path = SCREEN_PATH[step.screen];
    return pathname === path || pathname.startsWith(`${path}/`);
  });
}
