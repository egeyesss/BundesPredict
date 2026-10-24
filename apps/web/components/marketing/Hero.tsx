import Link from "next/link";

import { Wordmark } from "@/components/signature/Wordmark";
import { Button } from "@/components/ui/button";

import { HeroBackground } from "./HeroBackground";

export function Hero() {
  return (
    <section
      id="hero"
      aria-label="Introduction"
      data-landing-section="Top"
      className="relative isolate overflow-hidden border-b border-bp-border px-[max(16px,env(safe-area-inset-left,0px))]"
    >
      <HeroBackground />
      <div aria-hidden="true" className="hero-veil absolute inset-0 -z-10" />
      <div className="mx-auto grid max-w-[1160px] justify-items-center gap-[22px] py-[clamp(56px,9vw,112px)] text-center">
        <h1 aria-label="BundesPredict" className="m-0">
          <Wordmark size="hero" />
        </h1>
        <p className="m-0 max-w-[60ch] text-[clamp(17px,2vw,20px)] text-pretty text-bp-text">
          Win, draw and loss probabilities for every Bundesliga fixture, from a model refit every day. When news breaks, tell the
          agent what changed and watch the numbers move.
        </p>
        <div className="flex flex-wrap justify-center gap-2.5">
          <Button asChild size="lg">
            <Link href="/demo">Try the demo</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href="/login">Start free</Link>
          </Button>
        </div>
        <span className="font-mono text-xs text-bp-text-muted">3 free chats a day · no card needed</span>
      </div>
    </section>
  );
}
