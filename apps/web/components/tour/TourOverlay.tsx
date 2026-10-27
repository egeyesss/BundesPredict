"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore, type Dispatch } from "react";
import { createPortal } from "react-dom";

import { useReducedMotion } from "@/components/signature/reduced-motion";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { TourChatHandle } from "./chat-link";
import { SCREEN_LABEL, STEPS } from "./steps";
import type { TourAction, TourPhase } from "./tour-state";
import { useSpotlight } from "./useSpotlight";

import "./tour.css";

const subscribeNever = () => () => {};

const FOCUSABLE = "button:not([disabled]):not([hidden]), a[href]";
const WAITING_STEPS = new Set(["steps", "result", "chips"]);
const GIVE_UP_WAITING_MS = 45_000;
const MAX_RESTORE_FRAMES = 12;

type TourOverlayProps = {
  phase: Exclude<TourPhase, "idle">;
  index: number;
  chat: TourChatHandle | null;
  chatLimit: number;
  dispatch: Dispatch<TourAction>;
  onOpenCheckout: () => Promise<void>;
  checkoutPending: boolean;
};

export function TourOverlay(props: TourOverlayProps) {
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);
  if (!mounted) return null;
  return createPortal(<OverlayBody {...props} />, document.body);
}

function OverlayBody({ phase, index, chat, chatLimit, dispatch, onOpenCheckout, checkoutPending }: TourOverlayProps) {
  const reduced = useReducedMotion(false);
  const titleId = useId();
  const whatId = useId();
  const layer = useRef<HTMLDivElement>(null);
  const spot = useRef<HTMLDivElement>(null);
  const bubble = useRef<HTMLDivElement>(null);
  const arrow = useRef<HTMLSpanElement>(null);
  const welcome = useRef<HTMLDivElement>(null);
  const primary = useRef<HTMLButtonElement>(null);

  const step = STEPS[index];
  const tip = phase === "tip";
  const showingStep = phase !== "welcome";
  const anchor = useSpotlight(step, showingStep, { layer, spot, bubble, arrow }, reduced);

  const [hotspotId] = useState(() => (phase === "tip" ? STEPS[index].id : undefined));
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => {
      // A hotspot is rebuilt a frame or two after the overlay closes, so look for it a few times.
      let frames = 0;
      const restore = () => {
        const target =
          (opener?.isConnected && opener !== document.body ? opener : null) ??
          (hotspotId ? document.querySelector<HTMLElement>(`[data-tour-hotspot="${hotspotId}"]`) : null) ??
          (hotspotId ? null : document.querySelector<HTMLElement>("[data-demo-banner] button"));
        if (target) target.focus({ preventScroll: true });
        else if (++frames < MAX_RESTORE_FRAMES) requestAnimationFrame(restore);
        else document.querySelector<HTMLElement>("[data-demo-banner] button")?.focus({ preventScroll: true });
      };
      requestAnimationFrame(restore);
    };
  }, [hotspotId]);

  useEffect(() => {
    primary.current?.focus({ preventScroll: true });
  }, [phase, index]);

  useEffect(() => {
    const container = () => (showingStep ? bubble.current : welcome.current);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        dispatch({ type: "skip" });
        return;
      }
      if (phase === "tour" && event.key === "ArrowRight") {
        event.preventDefault();
        dispatch({ type: "next" });
      } else if (phase === "tour" && event.key === "ArrowLeft") {
        event.preventDefault();
        dispatch({ type: "back" });
      } else if (event.key === "Tab") {
        const focusable = [...(container()?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const inside = container()?.contains(document.activeElement) ?? false;
        if (!inside || (event.shiftKey && document.activeElement === first)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    const onFocusIn = (event: FocusEvent) => {
      const current = container();
      if (current && event.target instanceof Node && !current.contains(event.target)) primary.current?.focus({ preventScroll: true });
    };
    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("focusin", onFocusIn);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("focusin", onFocusIn);
    };
  }, [dispatch, phase, showingStep]);

  const waitingForAnswer = showingStep && anchor !== "found" && WAITING_STEPS.has(step.id) && chat?.status === "busy";
  const replay = chat?.replay;
  useEffect(() => {
    if (!waitingForAnswer || !replay) return;
    const timer = setTimeout(replay, GIVE_UP_WAITING_MS);
    return () => clearTimeout(timer);
  }, [waitingForAnswer, replay]);

  const closeOnBackdrop = tip ? () => dispatch({ type: "skip" }) : undefined;

  return (
    <div ref={layer} className="tour-layer" data-tour-layer data-reduced={reduced ? "" : undefined}>
      <div className="tour-blocker" data-dim={showingStep && anchor === "found" ? "false" : "true"} onClick={closeOnBackdrop} />

      {phase === "welcome" ? (
        <div ref={welcome} className="tour-welcome" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={whatId}>
          <span className="tour-eyebrow">Demo · about 3 minutes</span>
          <h2 id={titleId}>Take the tour</h2>
          <p id={whatId}>
            Fifteen short stops through the whole product. Each one says what you&apos;re looking at and how the number behind it is
            measured.
          </p>
          <ul>
            <li>Matchday odds and where they come from</li>
            <li>The agent, its steps and its limits</li>
            <li>The track record and the news edge</li>
            <li>The business side: revenue, costs, payments</li>
          </ul>
          <div className="tour-row">
            <Button ref={primary} size="lg" className="bg-bp-red text-white hover:bg-[#b80412]" onClick={() => dispatch({ type: "start" })}>
              Take the tour
            </Button>
            <Button size="lg" variant="secondary" onClick={() => dispatch({ type: "skip" })}>
              Look around first
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div ref={spot} className="tour-spot" style={{ display: "none" }} />
          <div ref={bubble} className="tour-bubble" data-side="center" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={whatId}>
            <span ref={arrow} className="tour-arrow" aria-hidden="true" />
            <div className="tour-top">
              <span className="tour-step" aria-live="polite">
                {tip ? "Quick tip" : `${index + 1} of ${STEPS.length} · ${SCREEN_LABEL[step.screen]}`}
              </span>
              {!tip && (
                <button type="button" className="tour-skip" onClick={() => dispatch({ type: "skip" })}>
                  Skip tour
                </button>
              )}
            </div>
            <h2 id={titleId}>{step.title}</h2>
            <p id={whatId} className="tour-what">
              {step.what}
            </p>
            <div className="tour-measure">
              <span>How it&apos;s measured</span>
              <p>{step.how}</p>
            </div>
            <StepExtras
              stepId={step.id}
              chat={chat}
              chatLimit={chatLimit}
              waiting={waitingForAnswer}
              onOpenCheckout={onOpenCheckout}
              checkoutPending={checkoutPending}
              anchorMissing={anchor === "missing"}
            />
            <div className="tour-foot">
              {tip ? (
                <span />
              ) : (
                <div className="tour-dots" aria-hidden="true">
                  {STEPS.map((candidate, dot) => (
                    <i key={candidate.id} className={cn(dot === index ? "on" : dot < index && "done")} />
                  ))}
                </div>
              )}
              <div className="tour-nav">
                {!tip && index > 0 && (
                  <Button size="sm" variant="secondary" onClick={() => dispatch({ type: "back" })}>
                    Back
                  </Button>
                )}
                <Button ref={primary} size="sm" className="bg-bp-red text-white hover:bg-[#b80412]" onClick={() => dispatch({ type: "next" })}>
                  {tip ? "Got it" : index === STEPS.length - 1 ? "Finish" : "Next"}
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

type StepExtrasProps = {
  stepId: string;
  chat: TourChatHandle | null;
  chatLimit: number;
  waiting: boolean;
  anchorMissing: boolean;
  onOpenCheckout: () => Promise<void>;
  checkoutPending: boolean;
};

/** Notes and actions that depend on the live state of the page behind a stop. */
function StepExtras({ stepId, chat, chatLimit, waiting, anchorMissing, onOpenCheckout, checkoutPending }: StepExtrasProps) {
  const notes: React.ReactNode[] = [];

  if (stepId === "message" && chat) {
    if (chat.status === "empty" && chat.canSend) {
      notes.push(
        <div key="send" className="tour-action">
          <Button size="sm" variant="secondary" onClick={chat.send}>
            Send this message
          </Button>
          <span>Uses 1 of your {chatLimit} demo chats. Or press Next to see a recorded answer instead.</span>
        </div>,
      );
    } else if (chat.status === "empty" && chat.outOfChats) {
      notes.push(
        <p key="out" className="tour-note">
          You&apos;ve used all {chatLimit} demo chats, so the next stops use a recorded answer.
        </p>,
      );
    } else if (chat.status === "busy" || chat.status === "done") {
      notes.push(
        <p key="sent" className="tour-note">
          {chat.recorded ? "This is a recorded example." : "Sent. Press Next to watch the agent work."}
        </p>,
      );
    }
  }

  if (chat?.recorded && (stepId === "steps" || stepId === "result" || stepId === "chips")) {
    notes.push(
      <p key="recorded" className="tour-note">
        <b>Recorded example.</b> This is a replay of a real answer, not a live one, and it did not use any of your chats.
      </p>,
    );
  }

  if (waiting && chat?.recorded) {
    notes.push(
      <p key="playing" role="status" className="tour-note">
        Playing the recorded answer…
      </p>,
    );
  } else if (waiting) {
    notes.push(
      <div key="waiting" className="tour-action" role="status">
        <span>Waiting for the agent to finish its answer…</span>
        <Button size="sm" variant="secondary" onClick={chat?.replay}>
          Show a recorded example instead
        </Button>
      </div>,
    );
  } else if (anchorMissing) {
    notes.push(
      <p key="missing" className="tour-note">
        This part of the page isn&apos;t showing right now, so there&apos;s nothing to highlight. Press Next to carry on.
      </p>,
    );
  }

  if (stepId === "upgrade") {
    notes.push(
      <div key="checkout" className="tour-action">
        <Button size="sm" variant="secondary" disabled={checkoutPending} onClick={() => void onOpenCheckout()}>
          {checkoutPending ? "Opening Stripe…" : "Open the Stripe test checkout"}
        </Button>
        <span>Next carries on without it. Coming back from Stripe offers to pick the tour up again.</span>
      </div>,
    );
  }

  return notes.length === 0 ? null : <div className="tour-extras">{notes}</div>;
}
