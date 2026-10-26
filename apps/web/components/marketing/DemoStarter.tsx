"use client";

import { AlertTriangle, UserRound } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { useSession } from "@/components/account/SessionProvider";
import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { createApiClient } from "@/lib/api/client";
import { ensureCsrfCookie, signOut } from "@/lib/auth/allauth";
import { navigate } from "@/lib/navigate";

type Phase = "starting" | "limited" | "failed";
type Limit = { code: string; message: string | null };

const LIMIT_COPY: Record<string, { title: string; message: string }> = {
  demo_budget: {
    title: "Today's demo spots are taken",
    message: "Every demo spot for today is used. They open up again at midnight UTC.",
  },
};
const IP_LIMIT_COPY = {
  title: "Too many demos from this network today",
  message: "Each network can start 3 demos a day. Try again tomorrow.",
};

/** Every refusal and failure leaves the visitor a way into the product. */
function WaysForward({ children }: { children?: ReactNode }) {
  return (
    <>
      {children}
      <Button asChild variant={children ? "secondary" : "default"}>
        <Link href="/login">Sign up free</Link>
      </Button>
      <Button asChild variant="secondary">
        <Link href="/matchday">Browse the matchday</Link>
      </Button>
      <Button asChild variant="secondary">
        <Link href="/track-record">See the track record</Link>
      </Button>
      <Button asChild variant="secondary">
        <Link href="/#demo">Watch the recorded replay</Link>
      </Button>
    </>
  );
}

type Outcome = { kind: "started" } | { kind: "limited"; limit: Limit } | { kind: "failed" };

async function requestDemo(): Promise<Outcome> {
  try {
    await ensureCsrfCookie();
    const { response, error } = await createApiClient({ baseUrl: window.location.origin }).POST("/api/v1/demo/start");
    if (response.status === 201) return { kind: "started" };
    if (response.status === 429) return { kind: "limited", limit: { code: error?.code ?? "demo_ip_limit", message: error?.message ?? null } };
    return { kind: "failed" };
  } catch {
    return { kind: "failed" };
  }
}

/** Asks the API for a throwaway demo account, then reloads into the matchday signed in as it. */
export function DemoStarter() {
  const { state: session } = useSession();
  const [phase, setPhase] = useState<Phase>("starting");
  const [limit, setLimit] = useState<Limit | null>(null);
  const [replacingSession, setReplacingSession] = useState(false);
  const started = useRef(false);

  const start = useCallback(() => {
    void requestDemo().then((outcome) => {
      if (outcome.kind === "started") return navigate("/matchday");
      if (outcome.kind === "limited") setLimit(outcome.limit);
      setPhase(outcome.kind);
    });
  }, []);

  useEffect(() => {
    if (session.status === "loading" || started.current) return;
    started.current = true;
    if (session.status === "ready") {
      if (session.me.is_demo) navigate("/matchday");
      return;
    }
    start();
  }, [session, start]);

  async function signOutThenStart() {
    setReplacingSession(true);
    setPhase("starting");
    const result = await signOut();
    if (result.ok) start();
    else setPhase("failed");
  }

  const signedInAs = session.status === "ready" && !session.me.is_demo && !replacingSession ? session.me.email : null;

  if (signedInAs === null && phase === "starting") {
    return (
      <p role="status" className="font-mono text-sm text-bp-text-muted">
        Setting up your demo…
      </p>
    );
  }

  if (signedInAs !== null) {
    return (
      <StateMessage
        icon={<UserRound className="size-4" />}
        title="You're already signed in"
        actions={
          <>
            <Button asChild>
              <Link href="/matchday">Back to the matchday</Link>
            </Button>
            <Button variant="secondary" onClick={() => void signOutThenStart()}>
              Sign out and start a demo
            </Button>
          </>
        }
      >
        You&apos;re signed in as {signedInAs}. A demo is a separate throwaway account, so starting one signs you out of this one first.
      </StateMessage>
    );
  }

  if (phase === "limited" && limit) {
    const copy = LIMIT_COPY[limit.code] ?? IP_LIMIT_COPY;
    return (
      <StateMessage tone="warn" icon={<AlertTriangle className="size-4" />} title={copy.title} actions={<WaysForward />}>
        <span>{limit.message ?? copy.message}</span> <span>Free accounts get 3 chats a day, and the matchday and track record are open to everyone.</span>
      </StateMessage>
    );
  }

  return (
    <StateMessage
      tone="warn"
      icon={<AlertTriangle className="size-4" />}
      title="Couldn't start the demo"
      actions={
        <WaysForward>
          <Button
            onClick={() => {
              setPhase("starting");
              start();
            }}
          >
            Try again
          </Button>
        </WaysForward>
      }
    >
      Something went wrong on our side. Try again in a moment, or sign up free.
    </StateMessage>
  );
}
