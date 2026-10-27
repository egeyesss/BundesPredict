import { DEMO } from "@/components/marketing/demo-content";
import happy from "@/lib/api/mocks/recorded/streams/happy.json";
import type { PredictStreamEvent } from "@/lib/api/types";

/** The recorded answer the landing page replays, reused when the tour has no live answer to point at. */
export const RECORDED_ANSWER = happy as unknown as PredictStreamEvent[];
export const RECORDED_QUESTION = DEMO.query;
export const RECORDED_MATCH = `${DEMO.home.name} v ${DEMO.away.name}`;
