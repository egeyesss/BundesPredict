import type { Metadata } from "next";

import { SignatureDemo } from "./SignatureDemo";

export const metadata: Metadata = {
  title: "Signature motion styleguide",
  robots: { index: false, follow: false },
};

export default function SignatureStyleguidePage() {
  return (
    <div className="mx-auto grid w-full max-w-[1160px] gap-12 px-4 pt-8 pb-20">
      <header className="grid gap-3">
        <span className="font-mono text-xs tracking-wider text-bp-text-muted uppercase">
          Styleguide · dev and preview builds only
        </span>
        <h1 className="font-display text-[clamp(44px,7vw,72px)] leading-none font-bold tracking-wide">Signature motion</h1>
        <p className="max-w-[70ch] text-bp-text-muted">
          The wordmark, the agent orb, the probability bars, adjustment chips and the stage ticker, driven by replayed agent
          streams.
        </p>
      </header>
      <SignatureDemo />
    </div>
  );
}
