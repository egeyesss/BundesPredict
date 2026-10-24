import type { Metadata } from "next";
import Link from "next/link";

import { ContactLink, LegalPage, LegalSection } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "Terms of use",
  description: "The rules for using BundesPredict: what the service is, plans and fair use, billing, and what it is not.",
  alternates: { canonical: "/legal/terms" },
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of use"
      intro="BundesPredict is a football analytics project run by one person. These terms are short on purpose."
    >
      <LegalSection title="Who runs it">
        <p className="m-0">
          BundesPredict is operated by Ege Yesilyurt, an individual based in Ontario, Canada. Questions about these terms go to <ContactLink />.
        </p>
      </LegalSection>

      <LegalSection title="What the service is">
        <p className="m-0">
          BundesPredict shows win, draw and loss probabilities and expected goals for Bundesliga fixtures, produced by a statistical model,
          and lets you ask an AI agent how news (a lineup, an injury, the weather) changes them. The agent can only nudge expected goals by
          small, capped amounts; the model recomputes every probability.
        </p>
        <p className="m-0">
          It is not betting advice. It is not a bookmaker, it does not take bets, it does not link to bookmakers, and nothing on the site
          tells you what to wager. Probabilities are estimates, they can be wrong, and the published backtest shows the model sits slightly
          behind the bookmakers&apos; closing line. Do not rely on them for any decision where you could lose money you cannot afford to lose.
        </p>
      </LegalSection>

      <LegalSection title="Accounts">
        <ul>
          <li>You sign in with Google or an email code. You must be at least 18 to use the service.</li>
          <li>Keep your sign-in method to yourself. You are responsible for what happens under your account.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Plans and fair use">
        <ul>
          <li>Free: 3 agent chats per day, counted per UTC day.</li>
          <li>Pro: 5 CAD per month, up to 100 agent chats per day. The cap exists to stop automated abuse, not to ration normal use.</li>
          <li>Matchday probabilities and the track record are free to read without an account.</li>
        </ul>
        <p className="m-0">
          Do not scrape the site, resell its output, probe the API with scripts, or try to get around the limits. I may rate limit or suspend
          accounts that do, and I may change the limits with notice on the site.
        </p>
      </LegalSection>

      <LegalSection title="Billing">
        <p className="m-0">
          Pro is billed monthly in Canadian dollars through Stripe and renews until you cancel. You can cancel at any time from your account
          page; Pro then stays active until the end of the period you already paid for. Taxes may be added where required. See the{" "}
          <Link href="/legal/refunds">refund policy</Link> for what happens if you are charged by mistake.
        </p>
      </LegalSection>

      <LegalSection title="Not affiliated with the league or clubs">
        <p className="m-0">
          BundesPredict is an independent project. It is not affiliated with, endorsed by or sponsored by DFL Deutsche Fußball Liga or the
          Bundesliga. Club names, crests and the Bundesliga logo are trademarks of their respective owners and appear only to say which
          competition and clubs the data covers.
        </p>
      </LegalSection>

      <LegalSection title="No warranty and limits on liability">
        <p className="m-0">
          The service is provided as is. I do not promise it will be available, accurate or free of errors. To the extent the law allows,
          I am not liable for losses that come from using the service, and my total liability to you for any claim is limited to what you
          paid me in the 12 months before it.
        </p>
      </LegalSection>

      <LegalSection title="Changes and ending">
        <p className="m-0">
          I may update these terms, and the date at the top will change when I do. You can stop using the service at any time. I may close
          an account that breaks these terms. The laws of Ontario and the federal laws of Canada that apply there govern these terms.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
