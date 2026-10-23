"use client";

import { useState, type KeyboardEvent, type ReactNode } from "react";

import { StateMessage } from "@/components/states/StateMessage";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RefreshCw, X } from "lucide-react";
import { useRouter } from "next/navigation";

import { BacktestPanel } from "./BacktestPanel";
import { LivePanel } from "./LivePanel";
import type { TrackRecordOutcome } from "./load";
import "./track-record.css";

type Tab = "live" | "backtest";

const TABS: { id: Tab; label: string }[] = [
  { id: "live", label: "This season" },
  { id: "backtest", label: "Backtest · 5 seasons" },
];

export function TrackRecordError() {
  const router = useRouter();
  return (
    <StateMessage
      tone="crit"
      icon={<X className="size-4" />}
      title="Couldn't load the track record"
      actions={
        <Button onClick={() => router.refresh()}>
          <RefreshCw /> Retry
        </Button>
      }
    >
      The connection to our server failed. The scores are stored safely and will be here when it is back.
    </StateMessage>
  );
}

export function TrackRecordView({ outcome }: { outcome: TrackRecordOutcome }) {
  const [tab, setTab] = useState<Tab>("live");

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = tab === "live" ? "backtest" : "live";
    setTab(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  let body: ReactNode;
  if (outcome.status === "error") {
    body = <TrackRecordError />;
  } else {
    body = (
      <>
        <div role="tablist" aria-label="Record" onKeyDown={onKeyDown} className="inline-flex w-max max-w-full gap-1 rounded-full border border-bp-border bg-bp-surface-1 p-1">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`tab-${item.id}`}
              aria-selected={tab === item.id}
              aria-controls={`panel-${item.id}`}
              tabIndex={tab === item.id ? 0 : -1}
              onClick={() => setTab(item.id)}
              className={cn(
                "touch-target rounded-full px-4 py-2 text-sm whitespace-nowrap text-bp-text-muted",
                tab === item.id && "bg-bp-text font-semibold text-bp-bg",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id="panel-live" aria-labelledby="tab-live" hidden={tab !== "live"} className="grid gap-7">
          <LivePanel record={outcome.record} onSeeBacktest={() => setTab("backtest")} />
        </div>
        <div role="tabpanel" id="panel-backtest" aria-labelledby="tab-backtest" hidden={tab !== "backtest"} className="grid gap-7">
          {tab === "backtest" && <BacktestPanel period={outcome.record.backtest} />}
        </div>
      </>
    );
  }

  return (
    <div className="track-record mx-auto grid w-full max-w-[1160px] gap-7 px-[max(16px,env(safe-area-inset-left))] pt-10 pb-20">
      <header className="grid gap-4">
        <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">Track record</span>
        <h1 className="font-display text-[clamp(44px,7vw,76px)] leading-[0.95] font-bold tracking-[0.01em] text-balance">How the model has done</h1>
        <p className="max-w-[64ch] text-[17px] text-bp-text-muted">
          Every prediction is frozen before kickoff and scored after the final whistle. Only the base model is scored: the agent&apos;s adjustments depend on news you bring, and there is no honest way to grade them against history.
        </p>
      </header>
      {body}
    </div>
  );
}
