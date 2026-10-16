import { delay } from "msw";
import { http, HttpResponse } from "msw/http";

import type { PredictRequest } from "../types";
import {
  adminMetrics,
  billingRedirects,
  conversationPage,
  fixtureCards,
  fixtureDetails,
  health,
  meFor,
  modelUnavailable,
  notFound,
  quotaExceeded,
  rateLimited,
  sampleConversation,
  teams,
  trackRecord,
} from "./data";
import { mockUsage } from "./state";
import { recordedStreams, sseResponse } from "./streams";

const API = "*/api/v1";

const cutOffStream = recordedStreams.happy.slice(0, 5);

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

export function createHandlers({ streamFrameDelayMs = 0 }: HandlerOptions = {}) {
  return [
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

    http.get(`${API}/me`, () => HttpResponse.json({ ...meFor("free"), usage: mockUsage.current() })),

    http.patch(`${API}/me`, async ({ request }) => {
      const changes = (await request.json()) as { email_opt_in?: boolean; timezone?: string | null };
      return HttpResponse.json({ ...meFor("free"), usage: mockUsage.current(), ...changes });
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

    http.get(`${API}/admin/metrics`, () => HttpResponse.json(adminMetrics)),

    http.post(`${API}/demo/start`, () => HttpResponse.json(meFor("demo"), { status: 201 })),

    http.post(`${API}/email/unsubscribe`, () => new HttpResponse(null, { status: 204 })),

    http.post(`${API}/predict/stream`, async ({ request }) => {
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
      if (scenario === "quota_exceeded" || mockUsage.isExhausted()) {
        return HttpResponse.json(quotaExceeded, { status: 402 });
      }

      if (scenario === "last_chat") mockUsage.leaveOneChat();
      const usage = mockUsage.spend();
      const recording = scenario === "cut_off" ? cutOffStream : recordedStreams[scenario];
      const events = recording.map((frame) => (frame.event === "quota" ? { ...frame, data: usage } : frame));

      await delay(streamFrameDelayMs);
      return sseResponse(events, { frameDelayMs: streamFrameDelayMs });
    }),
  ];
}

export const handlers = createHandlers();
