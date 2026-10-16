"use client";

import { useState } from "react";

import { Banner } from "@/components/states/Banner";
import { updateMe } from "@/lib/api/browser";
import type { Me } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { Card, Eyebrow } from "./AccountUi";

export function EmailCard({ me, onSaved }: { me: Me; onSaved: (me: Me) => void }) {
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const enabled = me.email_opt_in;

  const toggle = async () => {
    setPending(true);
    setFailed(false);
    try {
      onSaved(await updateMe({ email_opt_in: !enabled }));
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <Card aria-label="Email">
      <Eyebrow>Email</Eyebrow>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3.5">
        <div className="grid gap-1">
          <h2 id="email-toggle-label" className="font-display text-[19px] leading-tight font-semibold tracking-[0.02em]">
            Thursday matchday email
          </h2>
          <p className="text-[13px] text-bp-text-muted">
            The weekend&apos;s fixtures with the model&apos;s odds, every Thursday at 12:00 UTC. Unsubscribe from any email.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-labelledby="email-toggle-label"
          disabled={pending}
          onClick={() => void toggle()}
          className={cn(
            "relative h-[26px] w-11 flex-none rounded-full transition-colors outline-none focus-visible:ring-2 focus-visible:ring-bp-red-text focus-visible:ring-offset-2 focus-visible:ring-offset-bp-surface-1 disabled:opacity-60",
            enabled ? "bg-odds-win" : "bg-[#3F3F46]",
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              "absolute top-[3px] left-[3px] size-5 rounded-full bg-white transition-transform duration-200 ease-[cubic-bezier(0.34,1.3,0.64,1)] motion-reduce:transition-none",
              enabled && "translate-x-[18px]",
            )}
          />
        </button>
      </div>
      <p className="text-xs text-bp-text-muted" role="status">
        {enabled ? "On. The next one arrives Thursday at 12:00 UTC." : "Off. You won't get matchday emails."}
      </p>
      {failed && (
        <Banner tone="crit" role="alert" icon="!">
          Couldn&apos;t save that change. Check your connection and try again.
        </Banner>
      )}
    </Card>
  );
}
