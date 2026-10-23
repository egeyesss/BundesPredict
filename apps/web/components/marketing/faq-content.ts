export type FaqEntry = { id: string; question: string; answer: string };

export const FAQ_ENTRIES: readonly FaqEntry[] = [
  {
    id: "advice",
    question: "Is this betting advice?",
    answer:
      "No. BundesPredict is a football analytics project: it shows what a statistical model expects and how news changes that expectation. It doesn't link to bookmakers or tell you what to bet.",
  },
  {
    id: "source",
    question: "Where do the numbers come from?",
    answer:
      "A Dixon-Coles model fitted on Bundesliga results since 2020/21, with older matches weighted less. It is refit daily, so results from the weekend are in before the next matchday.",
  },
  {
    id: "agent",
    question: "What can the agent actually change?",
    answer:
      "Only expected goals, in small steps capped at ±0.60 each. The model then recomputes every probability from scratch, so the agent can't invent a number.",
  },
  {
    id: "good",
    question: "How good is the model?",
    answer:
      "Close to the bookmakers' closing line, and not better. Across 1,827 backtested matches its RPS is 0.2045 against the market's 0.1967. The track record page shows the live season as it happens.",
  },
  {
    id: "fair",
    question: "What counts as fair use on Pro?",
    answer: "Up to 100 chats a day. Nobody following the matchday gets near that; the cap is there to stop automated abuse.",
  },
];

const KEY_STEPS: Record<string, (index: number, count: number) => number> = {
  ArrowDown: (index) => index + 1,
  ArrowUp: (index) => index - 1,
  Home: () => 0,
  End: (_index, count) => count - 1,
};

/** The question to focus after `key`, wrapping at both ends; null for keys the list ignores. */
export function nextFaqIndex(key: string, index: number, count: number): number | null {
  const step = KEY_STEPS[key];
  return step ? (step(index, count) + count) % count : null;
}
