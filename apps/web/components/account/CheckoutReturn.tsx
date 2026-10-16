"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AgentOrb } from "@/components/signature/AgentOrb";
import { Button } from "@/components/ui/button";
import { fetchMe } from "@/lib/api/browser";
import type { Me } from "@/lib/api/types";
import { ApiFailure } from "@/lib/api/use-resource";
import { loginUrl } from "@/lib/auth/next-path";
import { navigate } from "@/lib/navigate";

import { Eyebrow } from "./AccountUi";
import { useSession } from "./SessionProvider";

const POLL_MS = 2000;
const SLOW_AFTER_MS = 20_000;
const GIVE_UP_AFTER_MS = 10 * 60_000;

type CheckoutReturnProps = {
  initialMe: Me;
  pollMs?: number;
  slowAfterMs?: number;
};

/**
 * Where Stripe sends the browser after paying. The plan only changes once Stripe's webhook has
 * reached Django, which can lag the redirect, so Pro is shown only when `/me` itself says so.
 */
export function CheckoutReturn({ initialMe, pollMs = POLL_MS, slowAfterMs = SLOW_AFTER_MS }: CheckoutReturnProps) {
  const [me, setMe] = useState(initialMe);
  const [slow, setSlow] = useState(false);
  const { setMe: shareMe } = useSession();
  const confirmed = me.plan === "pro";

  useEffect(() => {
    if (confirmed) return;
    const controller = new AbortController();
    const startedAt = Date.now();
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const fresh = await fetchMe(controller.signal);
        if (controller.signal.aborted) return;
        if (fresh.plan === "pro") {
          setMe(fresh);
          shareMe(fresh);
          return;
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiFailure && error.status === 401) {
          navigate(loginUrl("/account?checkout=success"));
          return;
        }
      }
      if (Date.now() - startedAt < GIVE_UP_AFTER_MS) timer = setTimeout(poll, pollMs);
    };

    timer = setTimeout(poll, pollMs);
    const slowTimer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => {
      controller.abort();
      clearTimeout(timer);
      clearTimeout(slowTimer);
    };
  }, [confirmed, pollMs, slowAfterMs, shareMe]);

  const heading = confirmed ? "You're on Pro" : slow ? "Still waiting on Stripe" : "Confirming your payment";
  const lede = confirmed
    ? "Unlimited chats are on. Your plan shows as Pro everywhere now."
    : slow
      ? "Your payment went through, but Stripe hasn't confirmed it to us yet. This page keeps checking, and you'll get a receipt by email either way. Nothing will be charged twice."
      : "Stripe has your payment. We're waiting for its confirmation before switching you to Pro.";

  return (
    <section aria-label="Payment confirmation" className="mx-auto grid w-full max-w-[460px] justify-items-center gap-[18px] px-4 pt-12 pb-16 text-center">
      <AgentOrb state={confirmed ? { phase: "done" } : { phase: "thinking" }} size={140} />
      <div className="grid gap-2" aria-live="polite">
        <Eyebrow>Back from Stripe</Eyebrow>
        <h1 className="font-display text-[34px] leading-none font-bold">{heading}</h1>
        <p className="text-bp-text-muted">{lede}</p>
      </div>
      <ul className="grid gap-1.5 text-left font-mono text-xs text-bp-text-muted">
        <li className="text-bp-text before:text-[var(--odds-win-text)] before:content-['✓_']">Checkout completed on Stripe</li>
        <li className={confirmed ? "text-bp-text before:text-[var(--odds-win-text)] before:content-['✓_']" : "before:text-bp-red-text before:content-['›_']"}>
          {confirmed ? "Stripe confirmed the subscription" : "Waiting for Stripe to confirm"}
        </li>
        <li className={confirmed ? "text-bp-text before:text-[var(--odds-win-text)] before:content-['✓_']" : "before:text-bp-red-text before:content-['›_']"}>
          Switch your account to Pro
        </li>
      </ul>
      {confirmed ? (
        <div className="flex flex-wrap justify-center gap-2">
          <Button asChild size="lg" className="bg-bp-red text-white hover:bg-[#b80412]">
            <Link href="/chat">Back to chat</Link>
          </Button>
          <Button asChild variant="secondary" size="lg">
            <Link href="/account">Account</Link>
          </Button>
        </div>
      ) : (
        slow && (
          <Button asChild variant="secondary" size="lg">
            <Link href="/account">Go to account</Link>
          </Button>
        )
      )}
    </section>
  );
}
