import { createApiClient, type ApiClient } from "./client";
import type { Conversation, ConversationPage, FixtureCard, FixtureDetail, Me, MeUpdate, Team } from "./types";
import { ApiFailure } from "./use-resource";

let client: ApiClient | null = null;

/** The origin is absolute so requests also resolve outside a browser, such as under Vitest. */
export function browserOrigin(): string {
  return window.location.origin;
}

function api(): ApiClient {
  client ??= createApiClient({ baseUrl: browserOrigin() });
  return client;
}

type Answer<T> = { data?: T; error?: { code: string; message: string }; response: Response };

function unwrap<T>({ data, error, response }: Answer<T>): T {
  if (data !== undefined && response.ok) return data;
  throw new ApiFailure(response.status, error?.code ?? "unexpected_response", error?.message ?? `The API answered ${response.status}.`);
}

export async function fetchMe(signal: AbortSignal): Promise<Me> {
  return unwrap(await api().GET("/api/v1/me", { signal }));
}

export async function fetchFixture(id: number, signal: AbortSignal): Promise<FixtureDetail> {
  return unwrap(await api().GET("/api/v1/fixtures/{id}", { params: { path: { id } }, signal }));
}

export async function fetchWeekFixtures(signal: AbortSignal): Promise<FixtureCard[]> {
  return unwrap(await api().GET("/api/v1/fixtures", { params: { query: { scope: "week" } }, signal }));
}

export async function fetchConversations(signal: AbortSignal, cursor?: string): Promise<ConversationPage> {
  return unwrap(await api().GET("/api/v1/conversations", { params: { query: cursor ? { cursor } : {} }, signal }));
}

export async function fetchConversation(id: string, signal: AbortSignal): Promise<Conversation> {
  return unwrap(await api().GET("/api/v1/conversations/{id}", { params: { path: { id } }, signal }));
}

export async function fetchTeams(signal: AbortSignal): Promise<Team[]> {
  return unwrap(await api().GET("/api/v1/teams", { signal }));
}

export async function updateMe(changes: MeUpdate): Promise<Me> {
  return unwrap(await api().PATCH("/api/v1/me", { body: changes }));
}

/** Returns the Stripe Checkout URL, or the portal URL when the user is already Pro. */
export async function createCheckout(): Promise<string> {
  return unwrap(await api().POST("/api/v1/billing/checkout")).url;
}

export async function createPortal(): Promise<string> {
  return unwrap(await api().POST("/api/v1/billing/portal")).url;
}
