"use client";

import Link from "next/link";
import { useState } from "react";

import { Card, Eyebrow } from "@/components/account/AccountUi";
import { Banner } from "@/components/states/Banner";
import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { unsubscribeFromEmail } from "@/lib/api/browser";
import { ApiFailure } from "@/lib/api/use-resource";

type Step = "ask" | "done" | "invalid";

const ACCOUNT_LINK = (
  <Button asChild variant="secondary" size="lg">
    <Link href="/account">Account settings</Link>
  </Button>
);

export function UnsubscribeCard({ token }: { token: string | null }) {
  const [step, setStep] = useState<Step>(token === null ? "invalid" : "ask");
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  const unsubscribe = async () => {
    if (token === null) return;
    setPending(true);
    setFailed(false);
    try {
      await unsubscribeFromEmail(token);
      setStep("done");
    } catch (error) {
      if (error instanceof ApiFailure && error.code === "invalid_token") setStep("invalid");
      else setFailed(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <Card aria-label="Unsubscribe" className="w-full max-w-[460px]">
      <Eyebrow>Email</Eyebrow>
      {step === "ask" && (
        <>
          <StateMessage as="h1" icon="@" title="Stop the Thursday matchday email?">
            You&apos;ll stop getting the weekend&apos;s fixtures with the model&apos;s odds. You can turn it back on from your account settings.
          </StateMessage>
          <div>
            <Button size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" disabled={pending} onClick={() => void unsubscribe()}>
              Unsubscribe
            </Button>
          </div>
          {failed && (
            <Banner tone="crit" role="alert" icon="!">
              Couldn&apos;t reach BundesPredict. Check your connection and try again.
            </Banner>
          )}
        </>
      )}
      {step === "done" && (
        <StateMessage as="h1" icon="✓" title="You're unsubscribed" actions={ACCOUNT_LINK}>
          No more matchday emails. The switch on your account page is now off.
        </StateMessage>
      )}
      {step === "invalid" && (
        <StateMessage as="h1" tone="warn" icon="!" title="This link doesn't work" actions={ACCOUNT_LINK}>
          The unsubscribe link is incomplete or changed. Sign in and switch the Thursday matchday email off from your account settings.
        </StateMessage>
      )}
    </Card>
  );
}
