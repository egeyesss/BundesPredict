"use client";

import { useCallback, useState } from "react";

import { createCheckout, createPortal } from "@/lib/api/browser";
import { loginUrl } from "@/lib/auth/next-path";
import { navigate } from "@/lib/navigate";
import { ApiFailure } from "@/lib/api/use-resource";

export type BillingKind = "checkout" | "portal";

function messageFor(error: unknown): string {
  if (error instanceof ApiFailure && error.code === "no_billing_account") {
    return "This account has no billing history yet. Upgrade to Pro first.";
  }
  return "Couldn't reach Stripe. Try again in a moment.";
}

/** Starts a Checkout or portal session and leaves for Stripe. `pending` stays set until the page unloads. */
export function useBillingRedirect({ onError }: { onError?: (message: string) => void } = {}) {
  const [pending, setPending] = useState<BillingKind | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async (kind: BillingKind) => {
      setPending(kind);
      setError(null);
      try {
        navigate(await (kind === "checkout" ? createCheckout() : createPortal()));
      } catch (failure) {
        if (failure instanceof ApiFailure && failure.status === 401) {
          navigate(loginUrl("/account"));
          return;
        }
        const message = messageFor(failure);
        setPending(null);
        setError(message);
        onError?.(message);
      }
    },
    [onError],
  );

  return { start, pending, error };
}
