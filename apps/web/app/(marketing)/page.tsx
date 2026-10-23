import type { Metadata } from "next";

import { AskDemo } from "@/components/marketing/AskDemo";
import { compactDemoStream } from "@/components/marketing/demo-replay";
import { Coverage } from "@/components/marketing/Coverage";
import { Faq } from "@/components/marketing/Faq";
import { Hero } from "@/components/marketing/Hero";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { Pricing } from "@/components/marketing/Pricing";
import { Section, SectionHead } from "@/components/marketing/Section";
import { SectionObserver } from "@/components/marketing/SectionObserver";
import { TrackRecordTeaser } from "@/components/marketing/TrackRecordTeaser";
import happy from "@/lib/api/mocks/recorded/streams/happy.json";
import type { PredictStreamEvent } from "@/lib/api/types";

export const metadata: Metadata = {
  title: { absolute: "BundesPredict | Bundesliga win probabilities, adjusted for the news" },
  description:
    "Win, draw and loss probabilities and expected goals for every Bundesliga fixture, from a calibrated model. Tell the agent what changed and see exactly how the numbers move.",
  alternates: { canonical: "/" },
};

const demoStream = compactDemoStream(happy as unknown as PredictStreamEvent[]);

export default function LandingPage() {
  return (
    <>
      <SectionObserver />
      <Hero />
      <Section id="demo" name="Demo">
        <AskDemo stream={demoStream} />
      </Section>
      <HowItWorks />
      <Coverage />
      <Section id="record" name="Track record">
        <SectionHead
          id="record"
          eyebrow="Track record"
          title="Close to the market, and honest about it"
          lede="Every number below is from predictions the model made before seeing the result. Lower ranked probability score (RPS) is better."
        />
        <TrackRecordTeaser />
      </Section>
      <Pricing />
      <Section id="faq" name="Questions">
        <SectionHead id="faq" eyebrow="Questions" title="Before you ask" centered />
        <Faq />
      </Section>
    </>
  );
}
