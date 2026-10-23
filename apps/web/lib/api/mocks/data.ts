import type {
  AdminMetrics,
  ApiError,
  BillingRedirect,
  Conversation,
  ConversationPage,
  FixtureCard,
  FixtureDetail,
  Me,
  PredictResponse,
  QuotaExceededError,
  Team,
  TrackRecord,
} from "../types";
import fixtureData from "./recorded/fixtures.json";
import teamData from "./recorded/teams.json";
import { recordedStreams } from "./streams";

export const health = { status: "ok", model_run_id: 57, db: "ok" } as const;

export const teams = teamData as Team[];

export const fixtureCards = fixtureData.cards as unknown as FixtureCard[];

export const fixtureDetails = fixtureData.details as unknown as Record<string, FixtureDetail>;

const RESETS_AT = "2026-10-16T00:00:00Z";

const baseMe: Me = {
  id: 101,
  email: "sam.rivera@example.com",
  name: "Sam Rivera",
  plan: "free",
  role: "user",
  is_demo: false,
  usage: { used: 1, limit: 3, resets_at: RESETS_AT },
  subscription: null,
  email_opt_in: false,
  timezone: "America/Toronto",
};

export function meFor(plan: Me["plan"]): Me {
  switch (plan) {
    case "free":
      return baseMe;
    case "pro":
      return {
        ...baseMe,
        plan: "pro",
        usage: { used: 12, limit: 100, resets_at: RESETS_AT },
        subscription: {
          status: "active",
          current_period_end: "2026-11-02T14:05:00Z",
          cancel_at_period_end: false,
        },
        email_opt_in: true,
      };
    case "demo":
      return {
        ...baseMe,
        id: 102,
        email: "demo-4f9a2c@demo.bundespredict.example",
        name: null,
        plan: "demo",
        is_demo: true,
        usage: { used: 2, limit: 10, resets_at: RESETS_AT },
        timezone: null,
      };
  }
}

export const quotaExceeded: QuotaExceededError = {
  code: "quota_exceeded",
  message: "You have used all 3 chats for today.",
  usage: { used: 3, limit: 3, resets_at: RESETS_AT },
  upgrade_url: "/account",
};

export const notAuthenticated: ApiError = {
  code: "not_authenticated",
  message: "Sign in to continue.",
};

export const rateLimited: ApiError = {
  code: "rate_limited",
  message: "Too many requests. Try again in a minute.",
};

export const modelUnavailable: ApiError = {
  code: "model_unavailable",
  message: "No fitted model is available yet.",
};

export const notFound: ApiError = { code: "not_found", message: "Not found." };

const happyResult = recordedStreams.happy.find((e) => e.event === "result")?.data as
  | PredictResponse
  | undefined;
if (happyResult === undefined) throw new Error("The happy recording has no result event.");

export const sampleConversation: Conversation = {
  id: "7d2f0a3c-5b1e-4c8a-9a47-0e6f3b21c5d8",
  title: "Guirassy is out for Dortmund, how does that change Dortmund",
  fixture_id: 803,
  updated_at: "2026-10-15T09:41:12Z",
  messages: [
    {
      id: 1,
      role: "user",
      content: "Guirassy is out for Dortmund, how does that change Dortmund v Hoffenheim?",
      prediction: null,
      created_at: "2026-10-15T09:41:03Z",
    },
    {
      id: 2,
      role: "assistant",
      content: happyResult.explanation,
      prediction: happyResult,
      created_at: "2026-10-15T09:41:12Z",
    },
  ],
};

export const conversationPage: ConversationPage = {
  next: null,
  results: [
    {
      id: sampleConversation.id,
      title: sampleConversation.title,
      fixture_id: 803,
      updated_at: sampleConversation.updated_at,
    },
    {
      id: "2b8e5c71-0d34-4f6a-8c19-a3d7e90f1b42",
      title: "Is Leipzig v Freiburg a banker for the draw?",
      fixture_id: 807,
      updated_at: "2026-10-14T18:22:40Z",
    },
    {
      id: "c91a4d06-7e2b-4b3f-b5a8-61f0d3e87a95",
      title: "How has Union Berlin's form looked lately?",
      fixture_id: null,
      updated_at: "2026-10-12T20:05:09Z",
    },
  ],
};

export const billingRedirects: { checkout: BillingRedirect; portal: BillingRedirect } = {
  checkout: { url: "https://checkout.stripe.com/c/pay/cs_test_mock" },
  portal: { url: "https://billing.stripe.com/p/session/test_mock" },
};

function resolvedFixture(id: number, home: [string, string], away: [string, string], score: [number, number], probs: [number, number, number], rps: number) {
  const outcome = score[0] > score[1] ? "H" : score[0] < score[1] ? "A" : "D";
  const top = probs[0] >= probs[2] ? (probs[0] >= probs[1] ? "H" : "D") : probs[2] >= probs[1] ? "A" : "D";
  return {
    fixture_id: id,
    kickoff_utc: "2026-10-10T13:30:00Z",
    home: { name: home[0], code: home[1] },
    away: { name: away[0], code: away[1] },
    home_goals: score[0],
    away_goals: score[1],
    outcome: outcome as "H" | "D" | "A",
    p_home: probs[0],
    p_draw: probs[1],
    p_away: probs[2],
    rps,
    hit: outcome === top,
  };
}

function matchdayRow(matchday: number, rps: number, logLoss: number, hitRate: number) {
  return {
    season: "2627",
    matchday,
    n_fixtures: 9,
    n_resolved: 9,
    rps,
    log_loss: logLoss,
    hit_rate: hitRate,
    bookmaker_rps: Number((rps - 0.008).toFixed(4)),
    base_rate_rps: 0.2304,
    fixtures: [
      resolvedFixture(matchday * 10 + 1, ["Borussia Dortmund", "BVB"], ["SV Werder Bremen", "SVW"], [2, 2], [0.6524, 0.1859, 0.1617], 0.2259),
      resolvedFixture(matchday * 10 + 2, ["1899 Hoffenheim", "TSG"], ["Hamburger SV", "HSV"], [2, 3], [0.5081, 0.2242, 0.2677], 0.3972),
      resolvedFixture(matchday * 10 + 3, ["Bayern Munich", "FCB"], ["VfB Stuttgart", "VFB"], [5, 1], [0.6819, 0.1681, 0.15], 0.0618),
    ],
  };
}

function newsChat(
  id: number,
  home: [string, string],
  away: [string, string],
  outcome: "H" | "D" | "A",
  hoursBefore: number,
  opening: number,
  agent: number,
  closing: number | null,
) {
  const judged = closing !== null;
  const ahead = judged && Math.abs(agent - closing) < Math.abs(closing - opening) && Math.sign(agent - opening) === Math.sign(closing - opening);
  return {
    prediction_id: id,
    fixture_id: id,
    matchday: id,
    kickoff_utc: "2026-10-10T13:30:00Z",
    logged_at: "2026-10-09T11:30:00Z",
    hours_before_kickoff: hoursBefore,
    home: { name: home[0], code: home[1] },
    away: { name: away[0], code: away[1] },
    outcome,
    agent,
    opening: judged ? opening : null,
    closing,
    ahead: judged ? ahead : null,
    verdict: judged ? (ahead ? "ahead of the market" : "market went the other way") : "waiting for the closing line",
  };
}

export const trackRecord: TrackRecord = {
  season: null,
  live: {
    kind: "live",
    label: "Live since 2026-08-28",
    since: "2026-08-28",
    model: { n_fixtures: 63, rps: 0.2086, log_loss: 0.9931, hit_rate: 0.5238 },
    bookmaker: { n_fixtures: 63, rps: 0.2012, log_loss: 0.9714, hit_rate: 0.5397 },
    base_rate: { n_fixtures: 63, rps: 0.2304, log_loss: 1.0602, hit_rate: 0.4127 },
    calibration_error: null,
    forecasters: [],
  },
  backtest: {
    kind: "backtest",
    label: "Backtest, 5 seasons",
    since: null,
    model: { n_fixtures: 1827, rps: 0.2045, log_loss: 1.001, hit_rate: null },
    bookmaker: { n_fixtures: 1827, rps: 0.1967, log_loss: 0.9744, hit_rate: null },
    base_rate: null,
    calibration_error: 0.0105,
    forecasters: [
      { key: "market_close", label: "Closing market", kind: "market", rps: 0.1967, log_loss: 0.9744, serving: false },
      { key: "market_open", label: "Opening market", kind: "market", rps: 0.1976, log_loss: 0.9775, serving: false },
      { key: "model_calibrated", label: "Model (calibrated)", kind: "model", rps: 0.2045, log_loss: 1.001, serving: true },
      { key: "model_uncalibrated", label: "Model (uncalibrated)", kind: "model", rps: 0.2046, log_loss: 1.0019, serving: false },
      { key: "model_xg", label: "Model + pre-match xG", kind: "model", rps: 0.2069, log_loss: 1.0116, serving: false },
    ],
  },
  matchdays: [
    matchdayRow(7, 0.1973, 0.9602, 0.5556),
    matchdayRow(6, 0.2284, 1.0518, 0.4444),
    matchdayRow(5, 0.2031, 0.9877, 0.5556),
    matchdayRow(4, 0.2147, 1.0044, 0.5556),
    matchdayRow(3, 0.1895, 0.9321, 0.6667),
    matchdayRow(2, 0.2216, 1.0187, 0.4444),
    matchdayRow(1, 0.1958, 0.9769, 0.4444),
  ],
  calibration: [
    { lower: 0.0, upper: 0.1, predicted_mean: 0.067, observed_rate: 0.083, count: 24 },
    { lower: 0.1, upper: 0.2, predicted_mean: 0.152, observed_rate: 0.136, count: 22 },
    { lower: 0.2, upper: 0.3, predicted_mean: 0.248, observed_rate: 0.265, count: 34 },
    { lower: 0.3, upper: 0.4, predicted_mean: 0.341, observed_rate: 0.312, count: 32 },
    { lower: 0.4, upper: 0.5, predicted_mean: 0.447, observed_rate: 0.474, count: 19 },
    { lower: 0.5, upper: 0.6, predicted_mean: 0.548, observed_rate: 0.5, count: 18 },
    { lower: 0.6, upper: 0.7, predicted_mean: 0.652, observed_rate: 0.688, count: 16 },
    { lower: 0.7, upper: 0.8, predicted_mean: 0.744, observed_rate: 0.714, count: 14 },
    { lower: 0.8, upper: 0.9, predicted_mean: 0.839, observed_rate: 0.889, count: 9 },
    { lower: 0.9, upper: 1.0, predicted_mean: 0.921, observed_rate: 1.0, count: 1 },
  ],
  news_edge: {
    n_logged: 3,
    n_compared: 2,
    n_ahead: 1,
    minimum_for_rate: 20,
    rate: null,
    chats: [
      newsChat(1, ["Borussia Dortmund", "BVB"], ["Hamburger SV", "HSV"], "H", 26, 0.66, 0.7, 0.69),
      newsChat(2, ["SV Werder Bremen", "SVW"], ["RB Leipzig", "RBL"], "A", 48, 0.52, 0.46, 0.47),
      newsChat(3, ["Bayern Munich", "FCB"], ["VfB Stuttgart", "VFB"], "H", 3, 0.76, 0.8, null),
    ],
  },
};

export const newsEdgeEmpty: TrackRecord["news_edge"] = {
  n_logged: 0,
  n_compared: 0,
  n_ahead: 0,
  minimum_for_rate: 20,
  rate: null,
  chats: [],
};

export const adminMetrics: AdminMetrics = {
  generated_at: "2026-10-15T12:00:00Z",
  masked: false,
  active_subscribers: 12,
  mrr_cents: 6000,
  signups_7d: 9,
  signups_30d: 31,
  monthly_churn: 0.0833,
  chats_per_day: [
    { day: "2026-10-13", free: 14, pro: 22, demo: 6 },
    { day: "2026-10-14", free: 17, pro: 25, demo: 4 },
    { day: "2026-10-15", free: 9, pro: 18, demo: 3 },
  ],
  llm_cost_per_user_cents: 14.2,
  cost_to_revenue_per_pro_user: 0.19,
  webhook_failures: [
    {
      event_id: "evt_1QmockFailed01",
      type: "invoice.payment_failed",
      livemode: false,
      error: "Subscription row not found yet; retried after 2 minutes.",
      received_at: "2026-10-14T16:03:55Z",
    },
  ],
  failed_payments: [
    { email: "a.keller@example.com", amount_cents: 500, failed_at: "2026-10-14T16:03:50Z" },
  ],
};
