"use client";

import { useMemo, useState } from "react";

import { Banner } from "@/components/states/Banner";
import { Button } from "@/components/ui/button";
import { browserTimeZone, timeZoneOptions } from "@/lib/account/timezone";
import { updateMe } from "@/lib/api/browser";
import type { Me } from "@/lib/api/types";

import { Card, Eyebrow } from "./AccountUi";

export function TimeZoneCard({ me, onSaved }: { me: Me; onSaved: (me: Me) => void }) {
  const detected = browserTimeZone();
  const current = me.timezone ?? detected ?? "UTC";
  const options = useMemo(() => timeZoneOptions([me.timezone, detected]), [me.timezone, detected]);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  const save = async (change: () => Promise<Me>) => {
    setPending(true);
    setFailed(false);
    try {
      onSaved(await change());
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  const choose = (zone: string) => save(() => updateMe({ timezone: zone, timezone_source: "manual" }));

  // `null` hands control back to the browser; the follow-up report then fills the zone in again.
  const resetToBrowserZone = () =>
    save(async () => {
      await updateMe({ timezone: null });
      return updateMe({ timezone: detected });
    });

  return (
    <Card aria-label="Time zone">
      <Eyebrow>Time zone</Eyebrow>
      <div className="grid gap-1.5">
        <label htmlFor="time-zone" className="text-[13px] text-bp-text-muted">
          Time zone
        </label>
        <select
          id="time-zone"
          value={current}
          disabled={pending}
          onChange={(event) => void choose(event.target.value)}
          className="h-11 w-full rounded-lg border border-input bg-card px-3 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60"
        >
          {options.map((zone) => (
            <option key={zone} value={zone}>
              {zone.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs text-bp-text-muted">Kickoff times and your daily reset follow this zone.</p>
      {detected && me.timezone !== null && me.timezone !== detected && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-bp-text-muted">
          <span>Your browser says {detected.replaceAll("_", " ")}.</span>
          <Button variant="secondary" size="sm" disabled={pending} onClick={() => void resetToBrowserZone()}>
            Use browser time zone
          </Button>
        </div>
      )}
      {failed && (
        <Banner tone="crit" role="alert" icon="!">
          Couldn&apos;t save the time zone. Try again.
        </Banner>
      )}
    </Card>
  );
}
