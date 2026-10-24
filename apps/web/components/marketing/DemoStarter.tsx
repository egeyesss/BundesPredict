"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { createApiClient } from "@/lib/api/client";
import { navigate } from "@/lib/navigate";

type Phase = "starting" | "rate_limited" | "failed";

/** Asks the API for a throwaway demo account, then reloads into the matchday signed in as it. */
export function DemoStarter() {
  const [phase, setPhase] = useState<Phase>("starting");
  const started = useRef(false);

  const start = useCallback(async () => {
    setPhase("starting");
    try {
      const { response } = await createApiClient({ baseUrl: window.location.origin }).POST("/api/v1/demo/start");
      if (response.status === 201) return navigate("/matchday");
      setPhase(response.status === 429 ? "rate_limited" : "failed");
    } catch {
      setPhase("failed");
    }
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start();
  }, [start]);

  if (phase === "starting") {
    return (
      <p role="status" className="font-mono text-sm text-bp-text-muted">
        Setting up your demo…
      </p>
    );
  }

  return (
    <StateMessage
      tone="warn"
      icon={<AlertTriangle className="size-4" />}
      title={phase === "rate_limited" ? "Too many demos from this network today" : "Couldn't start the demo"}
      actions={
        phase === "rate_limited" ? (
          <Button asChild>
            <Link href="/login">Sign in with email</Link>
          </Button>
        ) : (
          <Button onClick={() => void start()}>Try again</Button>
        )
      }
    >
      {phase === "rate_limited"
        ? "Each network can start a few demos a day. Signing in with an email gives you 3 free chats a day instead."
        : "Something went wrong on our side. Try again in a moment, or sign in with an email."}
    </StateMessage>
  );
}
