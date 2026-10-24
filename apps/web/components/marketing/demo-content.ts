import type { CrestTeam } from "@/components/brand/ClubCrest";

/** The question that produced `lib/api/mocks/recorded/streams/happy.json`. */
export const DEMO = {
  query: "Guirassy is out for Dortmund, how does that change Dortmund v Hoffenheim?",
  home: { name: "Dortmund", code: "BVB" },
  away: { name: "Hoffenheim", code: "TSG" },
} as const satisfies { query: string; home: CrestTeam; away: CrestTeam };
