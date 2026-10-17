"use client";

import { useCallback, useState } from "react";

import { signOut as requestSignOut } from "@/lib/auth/allauth";
import { navigate } from "@/lib/navigate";

/** Ends the session, then reloads onto the login page so no signed-in page state survives. */
export function useSignOut({ onError }: { onError?: (message: string) => void } = {}) {
  const [pending, setPending] = useState(false);

  const signOut = useCallback(async () => {
    setPending(true);
    const result = await requestSignOut();
    if (result.ok) {
      navigate("/login");
      return;
    }
    setPending(false);
    onError?.("Couldn't sign you out. Check your connection and try again.");
  }, [onError]);

  return { signOut, pending };
}
