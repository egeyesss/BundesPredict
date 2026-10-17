import type { Metadata } from "next";

import { ClubCrest } from "@/components/brand/ClubCrest";
import { LeagueMark } from "@/components/brand/LeagueMark";

import { CrestSheet } from "./CrestSheet";
import { IslandPreviews } from "./IslandPreviews";
import { Primitives } from "./Primitives";
import { Section } from "./Section";
import { TokenSwatches } from "./TokenSwatches";
import { TypeRoles } from "./TypeRoles";

export const metadata: Metadata = {
  title: "Styleguide",
  robots: { index: false, follow: false },
};

export default function StyleguidePage() {
  return (
    <div className="mx-auto grid w-full max-w-[1160px] gap-12 px-4 pt-8 pb-20">
      <header className="grid gap-3">
        <span className="font-mono text-xs tracking-wider text-bp-text-muted uppercase">
          Styleguide · dev and preview builds only
        </span>
        <h1 className="font-display text-[clamp(44px,7vw,72px)] leading-none font-bold tracking-wide">Design system</h1>
        <p className="max-w-[70ch] text-bp-text-muted">
          Every token, type role, primitive, brand mark and nav layout in one place.
        </p>
      </header>

      <Section id="tokens" title="Tokens" note="Read straight from tokens.css, so this list cannot drift from the stylesheet.">
        <TokenSwatches />
      </Section>

      <Section id="odds" title="Odds roles" note="Colour follows likelihood, never home or away. Only the leading outcome gets full colour.">
        <div className="grid gap-3 rounded-lg border border-bp-border bg-bp-surface-1 p-4">
          <div className="flex h-2 gap-0.5" aria-hidden="true">
            <span className="rounded-[2px] bg-odds-win" style={{ flex: 64 }} />
            <span className="rounded-[2px] bg-odds-draw" style={{ flex: 19 }} />
            <span className="rounded-[2px] bg-odds-lose" style={{ flex: 17 }} />
          </div>
          <p className="font-mono text-sm">
            <span className="font-semibold text-odds-win-text">Bayern 64%</span>
            <span className="text-bp-text-muted"> · Draw 19% · Leipzig 17% · xG 2.61 – 1.14</span>
          </p>
          <p className="font-mono text-sm">
            <span className="text-bp-up">▲ +4.2</span> <span className="text-bp-down">▼ −3.1</span>
          </p>
        </div>
      </Section>

      <Section id="type" title="Type" note="Display text is uppercase only for short labels, never for sentences.">
        <TypeRoles />
      </Section>

      <Section id="primitives" title="Primitives" note="shadcn/ui restyled to the tokens.">
        <Primitives />
      </Section>

      <Section id="crests" title="Club crests" note="Self-hosted SVGs at the four sizes the app uses. The chip appears only when an asset is missing.">
        <CrestSheet />
        <div className="flex flex-wrap items-center gap-3 text-sm text-bp-text-muted">
          <ClubCrest team={{ name: "Bayern", code: "FCB" }} size={32} />
          Bayern 64%
          <ClubCrest team={{ name: "Dortmund", code: "BVB" }} size={32} />
          Dortmund 17%
        </div>
      </Section>

      <Section
        id="league"
        title="League mark"
        note="Only in the matchday header, the coverage section and the footer, never next to the wordmark. Shown unmodified on a white plate."
      >
        <div className="flex flex-wrap items-center gap-4">
          <LeagueMark placement="matchday-header" size={48} />
          <LeagueMark placement="matchday-header" size={64} />
        </div>
      </Section>

      <Section id="island" title="Island nav" note="Every layout the pill morphs between, signed out and signed in.">
        <IslandPreviews />
      </Section>
    </div>
  );
}
