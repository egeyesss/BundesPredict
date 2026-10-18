import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <div className="mx-auto grid w-full max-w-[520px] flex-1 content-center justify-items-center gap-3 px-4 py-16 text-center">
      <span aria-hidden="true" className="font-display text-[clamp(56px,16vw,88px)] leading-none font-bold tracking-[0.02em]">
        Off<b className="text-bp-red">side</b>
      </span>
      <h1 className="font-display text-[26px] leading-tight font-semibold tracking-[0.02em]">That page isn&apos;t on the team sheet</h1>
      <p className="max-w-[42ch] text-bp-text-muted">The link may be old or mistyped. The matchday page has every fixture this week.</p>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        <Button asChild size="lg">
          <Link href="/matchday">Matchday</Link>
        </Button>
        <Button asChild size="lg" variant="secondary">
          <Link href="/">Home</Link>
        </Button>
      </div>
    </div>
  );
}
