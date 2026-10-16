import type { Metadata } from "next";

import { AccountView } from "@/components/account/AccountView";
import { CheckoutReturn } from "@/components/account/CheckoutReturn";
import { requireMe } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Account" };

export default async function AccountPage({ searchParams }: { searchParams: Promise<{ checkout?: string | string[] }> }) {
  const returning = (await searchParams).checkout === "success";
  const me = await requireMe(returning ? "/account?checkout=success" : "/account");
  return returning ? <CheckoutReturn initialMe={me} /> : <AccountView initialMe={me} />;
}
