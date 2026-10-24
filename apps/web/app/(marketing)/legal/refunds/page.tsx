import type { Metadata } from "next";

import { ContactLink, LegalPage, LegalSection } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: "Refund policy",
  description: "How cancelling Pro works and when a charge is refunded.",
  alternates: { canonical: "/legal/refunds" },
};

export default function RefundsPage() {
  return (
    <LegalPage title="Refund policy" intro="Pro is 5 CAD a month. Cancelling is one click, and mistakes get fixed.">
      <LegalSection title="Cancelling">
        <p className="m-0">
          Cancel any time from your account page. You keep Pro until the end of the month you already paid for, and you are not charged
          again after that.
        </p>
      </LegalSection>

      <LegalSection title="When you get your money back">
        <ul>
          <li>You were charged twice, or after you cancelled.</li>
          <li>You could not use Pro because of a fault on this side that was not fixed within a few days.</li>
          <li>You subscribed by accident and email within 14 days of the charge, having used few or no Pro chats.</li>
        </ul>
        <p className="m-0">
          Otherwise, a month that has been used is not refunded part way through. The Free plan is never charged.
        </p>
      </LegalSection>

      <LegalSection title="How to ask">
        <p className="m-0">
          Email <ContactLink /> from the address on your account and say which charge it is about. Refunds go back to the original card
          through Stripe and usually show up within 5 to 10 business days.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
