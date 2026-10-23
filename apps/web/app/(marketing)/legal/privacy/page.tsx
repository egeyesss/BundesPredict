import type { Metadata } from "next";

import { ContactLink, LegalPage, LegalSection } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "What BundesPredict stores about you, which services process it, and how to have it deleted.",
  alternates: { canonical: "/legal/privacy" },
};

const PROCESSORS = [
  ["Neon", "database hosting (accounts, chats, predictions, usage)"],
  ["Railway", "hosting for the Django API"],
  ["Vercel", "hosting for the website"],
  ["Resend", "sending sign-in codes and the matchday email"],
  ["Stripe", "payments and subscriptions"],
  ["Anthropic", "the language model behind the agent; your chat messages are sent to it to produce an answer"],
  ["Sentry", "error monitoring"],
] as const;

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      intro="What BundesPredict keeps about you, who else handles it, and how to get it deleted."
    >
      <LegalSection title="Who is responsible">
        <p className="m-0">
          Ege Yesilyurt, an individual based in Ontario, Canada, operates BundesPredict and is responsible for your data. Contact:{" "}
          <ContactLink />.
        </p>
      </LegalSection>

      <LegalSection title="What is kept">
        <ul>
          <li>Account: your email address, and your name if Google provides one.</li>
          <li>Chats: the messages you send the agent, its answers, and the predictions and adjustments behind each answer.</li>
          <li>Usage: how many chats you used on each day, and your plan.</li>
          <li>Billing: a Stripe customer ID and your subscription status. Card details go to Stripe and never reach this site.</li>
          <li>Email preferences: whether you opted in to the weekly matchday email.</li>
          <li>Technical data: your IP address (used for rate limiting) and error reports, which can include the page you were on and your browser type.</li>
        </ul>
        <p className="m-0">
          The site sets cookies for your session and for form security only. There are no advertising or analytics cookies.
        </p>
      </LegalSection>

      <LegalSection title="Why">
        <p className="m-0">
          To sign you in, answer your questions, enforce the daily limits, take payment, send the emails you asked for, and keep the service
          running and secure. Your data is not sold and is not used for advertising.
        </p>
      </LegalSection>

      <LegalSection title="Who else handles it">
        <ul>
          {PROCESSORS.map(([name, role]) => (
            <li key={name}>
              <strong>{name}</strong>: {role}.
            </li>
          ))}
        </ul>
        <p className="m-0">These services run in several countries, so your data can be processed outside Canada.</p>
      </LegalSection>

      <LegalSection title="How long it is kept">
        <ul>
          <li>Account, chats and usage stay until you ask for them to be deleted.</li>
          <li>Demo accounts and everything in them are deleted after 24 hours.</li>
          <li>Payment records may be kept by Stripe and by me for as long as tax and accounting rules require.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Your choices">
        <p className="m-0">
          Email <ContactLink /> to see what is stored about you, correct it, or delete your account and chats. The matchday email is off
          until you turn it on from your account page, and every email has an unsubscribe link that works in one click.
        </p>
      </LegalSection>

      <LegalSection title="Children and changes">
        <p className="m-0">
          The service is not meant for anyone under 18. If this policy changes, the date at the top changes with it.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
