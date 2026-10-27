import { delay } from "msw";
import { http, HttpResponse } from "msw/http";

import type { PredictRequest } from "../types";
import {
  billingRedirects,
  conversationPage,
  fixtureCards,
  fixtureDetails,
  health,
  meFor,
  notAuthenticated,
  modelUnavailable,
  notFound,
  quotaExceeded,
  rateLimited,
  sampleConversation,
  teams,
  trackRecord,
} from "./data";
import {
  MOCK_DEMO_START_COOKIE,
  clearMockSession,
  meChanges,
  meForMockPlan,
  mockCookie,
  mockPlanFrom,
  setMockCsrfCookie,
  setMockDemoExpiry,
  setMockSession,
} from "./session";
import { adminMetricsFor, ADMIN_RANGES } from "./admin";
import { mockDemoUsage, mockUsage } from "./state";
import { recordedStreams, sseResponse } from "./streams";

const API = "*/api/v1";

const cutOffStream = recordedStreams.happy.slice(0, 5);

const DEMO_LIFETIME_MS = 24 * 3600e3;
const DEMO_START_LIMITS: Record<string, { code: string; message: string } | undefined> = {
  ip_limit: { code: "demo_ip_limit", message: "This network has started its 3 demos for today. Try again tomorrow, or sign up free." },
  budget: { code: "demo_budget", message: "Today's demo spots are used up. They reset at midnight UTC, or you can sign up free." },
};

export type PredictScenario =
  | "happy"
  | "tool_heavy"
  | "last_chat"
  | "error"
  | "quota_exceeded"
  | "model_unavailable"
  | "rate_limited"
  | "cut_off";

/** Keywords in the query pick the scenario, so a dev can steer the mock from the chat box. */
export function scenarioForQuery(query: string): PredictScenario {
  if (/quota/i.test(query)) return "quota_exceeded";
  if (/unavailable/i.test(query)) return "model_unavailable";
  if (/rate.?limit/i.test(query)) return "rate_limited";
  if (/cut.?off/i.test(query)) return "cut_off";
  if (/error|fail/i.test(query)) return "error";
  if (/last chat/i.test(query)) return "last_chat";
  if (/kane|mainz|tool|weather/i.test(query)) return "tool_heavy";
  return "happy";
}

export interface HandlerOptions {
  /** Pause between SSE frames. Zero in tests, a few hundred ms in the browser. */
  streamFrameDelayMs?: number;
}

function validationError(message: string) {
  return HttpResponse.json({ code: "validation_error", message }, { status: 400 });
}

const ALLAUTH = "*/_allauth/browser/v1/auth";
const VALID_CODE = "BCDFGHJK";

type PendingFlow = { kind: "login_by_code" | "verify_email" } | null;
let pendingFlow: PendingFlow = null;

const pendingResponse = (flow: "login_by_code" | "verify_email") =>
  HttpResponse.json({ status: 401, data: { flows: [{ id: flow, is_pending: true }] }, meta: { is_authenticated: false } }, { status: 401 });

const codeMatches = (code: unknown) => typeof code === "string" && code.replace(/[^a-z]/gi, "").toUpperCase() === VALID_CODE;

const wrongCode = () =>
  HttpResponse.json({ status: 400, errors: [{ message: "Incorrect code.", code: "incorrect_code", param: "code" }] }, { status: 400 });

function signedIn() {
  setMockSession("free");
  setMockCsrfCookie();
  pendingFlow = null;
  return HttpResponse.json({ status: 200, data: { user: { id: 101 } }, meta: { is_authenticated: true } });
}

function emailRequestResponse(email: unknown, kind: "login_by_code" | "verify_email") {
  if (typeof email !== "string" || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return HttpResponse.json({ status: 400, errors: [{ message: "Enter a valid email address.", code: "invalid", param: "email" }] }, { status: 400 });
  }
  if (email === "limited@example.com") {
    return HttpResponse.json({ status: 429, errors: [{ message: "Too many requests.", code: "rate_limited" }] }, { status: 429 });
  }
  // allauth answers the same way whether or not the address has an account, so the mock does too.
  pendingFlow = { kind };
  return pendingResponse(kind);
}

export function createHandlers({ streamFrameDelayMs = 0 }: HandlerOptions = {}) {
  return [
    http.get(`${ALLAUTH}/session`, ({ cookies }) => {
      setMockCsrfCookie();
      return mockPlanFrom(cookies)
        ? HttpResponse.json({ status: 200, data: { user: { id: 101 } }, meta: { is_authenticated: true } })
        : HttpResponse.json({ status: 401, data: { flows: [] }, meta: { is_authenticated: false } }, { status: 401 });
    }),

    http.delete(`${ALLAUTH}/session`, () => {
      clearMockSession();
      return HttpResponse.json({ status: 401, data: { flows: [] }, meta: { is_authenticated: false } }, { status: 401 });
    }),

    http.post(`${ALLAUTH}/code/request`, async ({ request }) =>
      emailRequestResponse(((await request.json()) as { email?: unknown }).email, "login_by_code"),
    ),

    http.post(`${ALLAUTH}/code/confirm`, async ({ request }) => {
      if (pendingFlow?.kind !== "login_by_code") return HttpResponse.json({ status: 401, data: { flows: [] } }, { status: 401 });
      return codeMatches(((await request.json()) as { code?: unknown }).code) ? signedIn() : wrongCode();
    }),

    http.post(`${ALLAUTH}/signup`, async ({ request }) =>
      emailRequestResponse(((await request.json()) as { email?: unknown }).email, "verify_email"),
    ),

    http.post(`${ALLAUTH}/email/verify`, async ({ request }) => {
      if (pendingFlow?.kind !== "verify_email") return HttpResponse.json({ status: 401, data: { flows: [] } }, { status: 401 });
      return codeMatches(((await request.json()) as { key?: unknown }).key) ? signedIn() : wrongCode();
    }),

    http.get(`${API}/health`, () => HttpResponse.json(health)),

    http.get(`${API}/teams`, () => HttpResponse.json(teams)),

    http.get(`${API}/fixtures`, ({ request }) => {
      const scope = new URL(request.url).searchParams.get("scope") ?? "next_matchday";
      if (scope !== "next_matchday" && scope !== "week") {
        return validationError("scope: not a valid choice.");
      }
      return HttpResponse.json(fixtureCards);
    }),

    http.get(`${API}/fixtures/:id`, ({ params }) => {
      const detail = fixtureDetails[String(params.id)];
      return detail ? HttpResponse.json(detail) : HttpResponse.json(notFound, { status: 404 });
    }),

    http.get(`${API}/me`, ({ cookies }) => {
      const plan = mockPlanFrom(cookies);
      return plan ? HttpResponse.json({ ...meForMockPlan(plan, cookies), ...meChanges }) : HttpResponse.json(notAuthenticated, { status: 401 });
    }),

    http.patch(`${API}/me`, async ({ request, cookies }) => {
      const plan = mockPlanFrom(cookies);
      if (!plan) return HttpResponse.json(notAuthenticated, { status: 401 });
      const body = (await request.json()) as { email_opt_in?: boolean; timezone?: string | null };
      if (body.email_opt_in !== undefined) meChanges.email_opt_in = body.email_opt_in;
      if (body.timezone !== undefined) meChanges.timezone = body.timezone;
      return HttpResponse.json({ ...meForMockPlan(plan, cookies), ...meChanges });
    }),

    http.get(`${API}/conversations`, () => HttpResponse.json(conversationPage)),

    http.get(`${API}/conversations/:id`, ({ params }) =>
      params.id === sampleConversation.id
        ? HttpResponse.json(sampleConversation)
        : HttpResponse.json(notFound, { status: 404 }),
    ),

    http.delete(`${API}/conversations/:id`, () => new HttpResponse(null, { status: 204 })),

    http.post(`${API}/billing/checkout`, () => HttpResponse.json(billingRedirects.checkout)),

    http.post(`${API}/billing/portal`, () => HttpResponse.json(billingRedirects.portal)),

    http.get(`${API}/track-record`, () => HttpResponse.json(trackRecord)),

    http.get(`${API}/admin/metrics`, ({ cookies, request }) => {
      const plan = mockPlanFrom(cookies);
      if (!plan) return HttpResponse.json(notAuthenticated, { status: 401 });
      if (plan !== "admin" && plan !== "demo") {
        return HttpResponse.json({ code: "permission_denied", message: "You do not have permission to do that." }, { status: 403 });
      }
      const days = Number(new URL(request.url).searchParams.get("days") ?? 30);
      if (!(ADMIN_RANGES as readonly number[]).includes(days)) return validationError("days: Use one of 7, 30, 90.");
      return HttpResponse.json(adminMetricsFor(days, plan === "demo"));
    }),

    http.post(`${API}/demo/start`, ({ cookies }) => {
      const limit = DEMO_START_LIMITS[mockCookie(cookies, MOCK_DEMO_START_COOKIE) ?? ""];
      if (limit) return HttpResponse.json(limit, { status: 429 });
      const expiresAt = new Date(Date.now() + DEMO_LIFETIME_MS).toISOString();
      setMockSession("demo");
      setMockCsrfCookie();
      setMockDemoExpiry(expiresAt);
      mockDemoUsage.reset();
      return HttpResponse.json({ ...meFor("demo"), usage: mockDemoUsage.current(), demo_expires_at: expiresAt }, { status: 201 });
    }),

    http.post(`${API}/email/unsubscribe`, async ({ request }) => {
      const { token } = (await request.json()) as { token?: string };
      return token === "invalid-link"
        ? HttpResponse.json({ code: "invalid_token", message: "This unsubscribe link is not valid." }, { status: 400 })
        : new HttpResponse(null, { status: 204 });
    }),

    http.post(`${API}/predict/stream`, async ({ request, cookies }) => {
      const { query } = (await request.json()) as Partial<PredictRequest>;
      if (typeof query !== "string" || query.trim() === "" || query.length > 500) {
        return validationError("query: must be 1 to 500 characters.");
      }

      const scenario = scenarioForQuery(query);
      if (scenario === "model_unavailable") {
        return HttpResponse.json(modelUnavailable, { status: 503 });
      }
      if (scenario === "rate_limited") {
        return HttpResponse.json(rateLimited, { status: 429, headers: { "Retry-After": "3" } });
      }
      const plan = mockPlanFrom(cookies);
      const counter = plan === "demo" ? mockDemoUsage : mockUsage;
      if (scenario === "quota_exceeded") return HttpResponse.json(quotaExceeded, { status: 402 });
      if (counter.isExhausted()) {
        const usage = counter.current();
        const demoSpent = { ...quotaExceeded, usage, message: `You have used all ${usage.limit} demo chats.` };
        return HttpResponse.json(plan === "demo" ? demoSpent : quotaExceeded, { status: 402 });
      }

      if (scenario === "last_chat") counter.leaveOneChat();
      const usage = counter.spend();
      const recording = scenario === "cut_off" ? cutOffStream : recordedStreams[scenario];
      const events = recording.map((frame) => (frame.event === "quota" ? { ...frame, data: usage } : frame));

      await delay(streamFrameDelayMs);
      return sseResponse(events, { frameDelayMs: streamFrameDelayMs });
    }),
  ];
}

export const handlers = createHandlers();
