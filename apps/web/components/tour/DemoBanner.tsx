"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

const TICK_MS = 1000;
export const BANNER_HEIGHT_VAR = "--demo-bar-h";

export function formatCountdown(msLeft: number): string {
  const totalSeconds = Math.max(0, Math.floor(msLeft / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

type DemoBannerProps = {
  /** `Me.demo_expires_at`: when the account and its data are deleted. */
  expiresAt: string | null;
  onRestartTour: () => void;
};

/**
 * A fixed bar above the page for demo accounts. It publishes its height as `--demo-bar-h` so the
 * island nav and the full-height pages sit below it instead of under it.
 */
export function DemoBanner({ expiresAt, onRestartTour }: DemoBannerProps) {
  const bar = useRef<HTMLDivElement>(null);
  const deadline = expiresAt ? Date.parse(expiresAt) : null;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (deadline === null) return;
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [deadline]);

  useLayoutEffect(() => {
    const element = bar.current;
    if (!element) return;
    const root = document.documentElement.style;
    const publish = () => root.setProperty(BANNER_HEIGHT_VAR, `${element.offsetHeight}px`);
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(element);
    return () => {
      observer.disconnect();
      root.removeProperty(BANNER_HEIGHT_VAR);
    };
  }, []);

  const msLeft = deadline === null ? null : deadline - now;
  const ended = msLeft !== null && msLeft <= 0;

  return (
    <div
      ref={bar}
      data-demo-banner
      role="region"
      aria-label="Demo mode"
      className="fixed inset-x-0 top-[env(safe-area-inset-top,0px)] z-30 flex items-center justify-center gap-x-3 border-b border-[#3A2A06] bg-[#1A1405] py-1.5 pr-[max(8px,env(safe-area-inset-right,0px))] pl-[max(16px,env(safe-area-inset-left,0px))] text-[13px] leading-snug text-[#FCD34D]"
    >
      <p className="m-0 min-w-0 text-center">
        <b className="font-semibold text-[#FDE68A]">Demo mode:</b> payments use Stripe test cards, nothing is charged.{" "}
        {ended ? (
          <>
            This demo has ended.{" "}
            <Link href="/demo" className="font-semibold text-[#FDE68A] underline underline-offset-2">
              Start a new demo
            </Link>
          </>
        ) : (
          msLeft !== null && (
            <span className="whitespace-nowrap">
              Deleted in{" "}
              <span role="timer" className="font-mono text-xs tabular-nums">
                {formatCountdown(msLeft)}
              </span>
            </span>
          )
        )}
      </p>
      <button
        type="button"
        aria-label="Restart the tour"
        onClick={onRestartTour}
        className="touch-target grid size-7 shrink-0 place-items-center rounded-full border border-[#3A2A06] bg-[#2A1F08] text-[13px] leading-none font-semibold text-[#FDE68A] hover:bg-[#3A2A06]"
      >
        ?
      </button>
    </div>
  );
}
