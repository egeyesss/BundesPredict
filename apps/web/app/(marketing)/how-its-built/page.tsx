import type { Metadata } from "next";
import Link from "next/link";

import { ArchitectureDiagram } from "@/components/marketing/ArchitectureDiagram";

export const metadata: Metadata = {
  title: "How it's built",
  description: "The architecture of BundesPredict: a pure Python model, a capped AI agent, a Django API and a Next.js front end.",
  alternates: { canonical: "/how-its-built" },
};

const REPO_URL = "https://github.com/egeyesss/BundesPredict";
const BACKTEST_URL = `${REPO_URL}/blob/main/reports/backtest_report.md`;

const BOUNDARIES = [
  {
    title: "The model owns probabilities, the agent owns language",
    body: "No endpoint, tool or serializer accepts a probability from the language model. The agent can only ask for expected-goals changes, and the engine clamps each one to ±0.60 before recomputing every market from the score grid.",
  },
  {
    title: "The library never imports Django",
    body: "packages/model is pure Python: no I/O, no database, no HTTP. The agent reaches data only through small protocols it defines, and the Django app supplies the implementations.",
  },
  {
    title: "Training never happens in a request",
    body: "A scheduled job refits the model and stores a new run. Serving reads the newest run, so every stored prediction points at the exact parameters that produced it.",
  },
  {
    title: "The web app knows who you are, and nothing else",
    body: "Plan, quota and entitlements are decided in Django, next to the agent that spends the tokens. The browser only ever talks to the Next.js origin, which proxies the API.",
  },
] as const;

export default function HowItsBuiltPage() {
  return (
    <article className="mx-auto grid w-full max-w-[1160px] gap-12 px-[max(16px,env(safe-area-inset-left,0px))] py-[clamp(40px,6vw,80px)]">
      <header className="grid max-w-[68ch] gap-3">
        <h1 className="m-0 font-display text-[clamp(40px,6vw,60px)] leading-none font-bold tracking-[0.01em]">How it&apos;s built</h1>
        <p className="m-0 text-[17px] text-bp-text-muted">
          A Dixon-Coles model produces the probabilities, an agent with a handful of tools explains how news changes them, and everything
          sits in one open repository. Here is how the pieces fit.
        </p>
      </header>

      <section aria-labelledby="diagram-title" className="grid gap-5">
        <h2 id="diagram-title" className="m-0 font-display text-[32px] leading-none font-semibold tracking-[0.02em]">
          The system
        </h2>
        <div className="rounded-xl border border-bp-border bg-bp-bg p-4 min-[700px]:p-6">
          <ArchitectureDiagram />
        </div>
      </section>

      <section aria-labelledby="boundaries-title" className="grid gap-5">
        <h2 id="boundaries-title" className="m-0 font-display text-[32px] leading-none font-semibold tracking-[0.02em]">
          Where the boundaries are
        </h2>
        <div className="grid gap-4 min-[861px]:grid-cols-2">
          {BOUNDARIES.map((boundary) => (
            <div key={boundary.title} className="grid content-start gap-2 rounded-xl border border-bp-border bg-bp-surface-1 p-5">
              <h3 className="m-0 font-display text-[22px] leading-[1.15] font-semibold tracking-[0.02em]">{boundary.title}</h3>
              <p className="m-0 text-[15px] text-bp-text-muted">{boundary.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="read-more-title" className="grid gap-4">
        <h2 id="read-more-title" className="m-0 font-display text-[32px] leading-none font-semibold tracking-[0.02em]">
          Read the source
        </h2>
        <ul className="m-0 grid list-none gap-3 p-0 text-[16px]">
          <li>
            <a className="underline underline-offset-4" href={REPO_URL}>
              The repository on GitHub
            </a>
            <span className="text-bp-text-muted"> for the model, the agent, the API and this site.</span>
          </li>
          <li>
            <a className="underline underline-offset-4" href={BACKTEST_URL}>
              The backtest report
            </a>
            <span className="text-bp-text-muted"> with the walk-forward method and the honest comparison to the market.</span>
          </li>
          <li>
            <Link className="underline underline-offset-4" href="/track-record">
              The track record
            </Link>
            <span className="text-bp-text-muted"> for predictions frozen before kickoff and scored afterwards.</span>
          </li>
        </ul>
      </section>
    </article>
  );
}
