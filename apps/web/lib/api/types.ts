import type { components } from "./schema";

type Schemas = components["schemas"];

export type Team = Schemas["Team"];
export type FixtureCard = Schemas["FixtureCard"];
export type FixtureDetail = Schemas["FixtureDetail"];
export type Markets = Schemas["Markets"];
export type AppliedAdjustment = Schemas["AppliedAdjustment"];
export type PredictRequest = Schemas["PredictRequest"];
export type PredictResponse = Schemas["PredictResponse"];
export type Me = Schemas["Me"];
export type MeUpdate = Schemas["PatchedMeUpdate"];
export type Usage = Schemas["Usage"];
export type ConversationSummary = Schemas["ConversationSummary"];
export type ConversationPage = Schemas["ConversationPage"];
export type Conversation = Schemas["Conversation"];
export type Message = Schemas["Message"];
export type TrackRecord = Schemas["TrackRecord"];
export type AdminMetrics = Schemas["AdminMetrics"];
export type BillingRedirect = Schemas["BillingRedirect"];

export type ApiError = Schemas["Error"];
export type QuotaExceededError = Schemas["QuotaExceededError"];

export type PredictStreamEvent = Schemas["PredictStreamFrame"];
export type StageEvent = Schemas["StageEventData"];
export type ToolCallStage = Schemas["ToolCallStage"];
export type ToolResultStage = Schemas["ToolResultStage"];

/** Tools the agent can call today. The API sends the name as a plain string. */
export const KNOWN_TOOL_NAMES = [
  "predict_match",
  "predict_match_with_context",
  "get_team_form",
  "lookup_player",
  "get_weather",
  "get_recent_results",
  "get_upcoming_fixtures",
] as const;
