import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/account/LoginForm";
import { safeNextPath } from "@/lib/auth/next-path";
import { getMe } from "@/lib/auth/server";

export const metadata: Metadata = { title: "Sign in" };

type LoginSearchParams = { next?: string | string[]; error?: string | string[]; key?: string | string[] };

export default async function LoginPage({ searchParams }: { searchParams: Promise<LoginSearchParams> }) {
  const params = await searchParams;
  const next = safeNextPath(params.next);
  const key = typeof params.key === "string" && params.key !== "" ? params.key : null;

  if (key === null && (await getMe()).status === "ok") redirect(next);

  return (
    <section aria-label="Sign in" className="grid flex-1 content-start justify-items-center px-4 pt-10 pb-16">
      <LoginForm next={next} socialError={params.error === "social"} emailKey={key} />
    </section>
  );
}
