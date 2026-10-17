"use client";

import { toast } from "sonner";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { browserTimeZone } from "@/lib/account/timezone";
import type { Me } from "@/lib/api/types";

import { Eyebrow } from "./AccountUi";
import { EmailCard } from "./EmailCard";
import { PlanCard } from "./PlanCard";
import { useSession } from "./SessionProvider";
import { TimeZoneCard } from "./TimeZoneCard";
import { UsageCard } from "./UsageCard";
import { useSignOut } from "./useSignOut";

export function AccountView({ initialMe }: { initialMe: Me }) {
  const [me, setLocalMe] = useState(initialMe);
  const { setMe: shareMe } = useSession();
  const { signOut, pending } = useSignOut({ onError: (message) => toast.error(message) });
  const timeZone = me.timezone ?? browserTimeZone();

  const saved = (next: Me) => {
    setLocalMe(next);
    shareMe(next);
  };

  return (
    <div className="mx-auto grid w-full max-w-[860px] gap-4 px-4 pt-8 pb-16">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="grid gap-1.5">
          <Eyebrow>Account</Eyebrow>
          <h1 className="font-display text-[clamp(36px,5vw,52px)] leading-none font-bold">{me.name ?? (me.is_demo ? "Demo visitor" : me.email)}</h1>
          <p className="text-bp-text-muted">{me.is_demo ? "Temporary demo account" : me.email}</p>
        </div>
        <Button variant="ghost" size="lg" className="border-bp-border" disabled={pending} onClick={() => void signOut()}>
          Sign out
        </Button>
      </div>
      <div className="grid items-start gap-4 min-[760px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <PlanCard me={me} timeZone={timeZone} />
        <UsageCard me={me} timeZone={timeZone} />
      </div>
      <div className="grid items-start gap-4 min-[760px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <EmailCard me={me} onSaved={saved} />
        <TimeZoneCard me={me} onSaved={saved} />
      </div>
    </div>
  );
}
