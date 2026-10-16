import type { Metadata } from "next";

import { MatchdayView } from "@/components/matchday/MatchdayView";
import { loadFixtures } from "@/lib/api/server";

export const metadata: Metadata = {
  title: "Matchday",
  description: "Model odds for every Bundesliga fixture this matchday, with expected goals.",
};

export default async function MatchdayPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const { scope: requested } = await searchParams;
  const scope = requested === "week" ? "week" : "next_matchday";
  return <MatchdayView outcome={await loadFixtures(scope)} scope={scope} />;
}
