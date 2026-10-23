import type { Metadata } from "next";

import { UnsubscribeCard } from "@/components/email/UnsubscribeCard";

export const metadata: Metadata = { title: "Unsubscribe", robots: { index: false, follow: false } };

export default async function UnsubscribePage({ searchParams }: { searchParams: Promise<{ t?: string | string[] }> }) {
  const { t } = await searchParams;
  const token = typeof t === "string" && t !== "" ? t : null;

  return (
    <section aria-label="Unsubscribe" className="grid flex-1 content-start justify-items-center px-4 pt-10 pb-16">
      <UnsubscribeCard token={token} />
    </section>
  );
}
