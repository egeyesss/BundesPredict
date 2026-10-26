"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from "react";
import { toast } from "sonner";

import { useSession } from "@/components/account/SessionProvider";
import { Button } from "@/components/ui/button";
import { createCheckout, fetchNextMatchdayFixtures } from "@/lib/api/browser";
import { groupByMatchday } from "@/lib/matchday";
import { navigate } from "@/lib/navigate";

import { TourChatLinkContext, type TourChatHandle, type TourChatLink } from "./chat-link";
import { DemoBanner } from "./DemoBanner";
import { Hotspots } from "./Hotspots";
import { SCREEN_PATH, STEPS, type TourStep } from "./steps";
import { TourOverlay } from "./TourOverlay";
import { INITIAL_TOUR, tourReducer, type TourAction, type TourState } from "./tour-state";
import { loadTour, markCheckoutStarted, saveTour, takeCheckoutResume } from "./tour-storage";

const REPLAY_STEPS = new Set(["steps", "result", "chips"]);
const UPGRADE_INDEX = STEPS.findIndex((step) => step.id === "upgrade");

const onScreen = (step: TourStep, pathname: string) => {
  const path = SCREEN_PATH[step.screen];
  return pathname === path || pathname.startsWith(`${path}/`);
};

function hrefFor(step: TourStep, fixtureId: number | null): string {
  return step.screen === "chat" && fixtureId !== null ? `/chat?fixture=${fixtureId}` : SCREEN_PATH[step.screen];
}

type Store = { loadedFor: number | null; tour: TourState; resumeOffered: boolean };
type StoreAction = TourAction | { type: "hydrate"; userId: number; saved: TourState | null } | { type: "offer-resume" } | { type: "close-resume" };

const INITIAL_STORE: Store = { loadedFor: null, tour: INITIAL_TOUR, resumeOffered: false };

function storeReducer(store: Store, action: StoreAction): Store {
  switch (action.type) {
    case "hydrate":
      return { ...store, loadedFor: action.userId, tour: action.saved ?? INITIAL_TOUR };
    case "offer-resume":
      return { ...store, resumeOffered: true };
    case "close-resume":
      return { ...store, resumeOffered: false };
    default:
      return { ...store, tour: tourReducer(store.tour, action) };
  }
}

/**
 * Everything the guided demo adds to a page: the banner, the tour and its hotspots. It renders
 * only for demo accounts, and always wraps the same children so a signed-in page never remounts.
 */
export function TourProvider({ children }: { children: ReactNode }) {
  const { state: session } = useSession();
  const me = session.status === "ready" && session.me.is_demo ? session.me : null;
  const userId = me?.id ?? null;
  const pathname = usePathname();
  const router = useRouter();

  const [store, dispatchStore] = useReducer(storeReducer, INITIAL_STORE);
  const { tour: state, loadedFor, resumeOffered } = store;
  const dispatch: Dispatch<TourAction> = dispatchStore;
  const [chat, setChat] = useState<TourChatHandle | null>(null);
  const [firstFixture, setFirstFixture] = useState<number | null | undefined>(undefined);
  const [checkoutPending, setCheckoutPending] = useState(false);
  const pushedFor = useRef<number | null>(null);
  const replayedFor = useRef<string | null>(null);

  const ready = userId !== null && loadedFor === userId;
  const step = STEPS[state.index];
  const touring = ready && (state.phase === "tour" || state.phase === "tip");

  useEffect(() => {
    if (userId === null) return;
    dispatchStore({ type: "hydrate", userId, saved: loadTour(userId) });
  }, [userId]);

  useEffect(() => {
    if (ready) saveTour(userId, state);
  }, [ready, userId, state]);

  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    fetchNextMatchdayFixtures(controller.signal).then(
      (fixtures) => setFirstFixture(groupByMatchday(fixtures)[0]?.fixtures[0]?.id ?? null),
      () => {
        if (!controller.signal.aborted) setFirstFixture(null);
      },
    );
    return () => controller.abort();
  }, [ready]);

  useEffect(() => {
    if (!ready || state.phase !== "tour") return;
    if (onScreen(step, pathname)) {
      pushedFor.current = null;
      return;
    }
    if (step.screen === "chat" && firstFixture === undefined) return;
    if (pushedFor.current === state.index) return;
    pushedFor.current = state.index;
    router.push(hrefFor(step, firstFixture ?? null));
  }, [ready, state.phase, state.index, step, pathname, firstFixture, router]);

  useEffect(() => {
    if (!touring || !chat || !REPLAY_STEPS.has(step.id)) return;
    if (chat.status === "empty" || chat.status === "failed") {
      const key = `${step.id}:${chat.status}`;
      if (replayedFor.current === key) return;
      replayedFor.current = key;
      chat.replay();
    } else {
      replayedFor.current = null;
    }
  }, [touring, chat, step.id]);

  useEffect(() => {
    if (!ready || userId === null || pathname !== "/account") return;
    if (!new URLSearchParams(window.location.search).has("checkout")) return;
    if (takeCheckoutResume(userId)) dispatchStore({ type: "offer-resume" });
  }, [ready, userId, pathname]);

  const openCheckout = useCallback(async () => {
    if (userId === null) return;
    setCheckoutPending(true);
    try {
      const url = await createCheckout();
      const leaving = { ...state, phase: "idle" as const, answered: true };
      dispatchStore({ type: "skip" });
      saveTour(userId, leaving);
      markCheckoutStarted(userId);
      navigate(url);
    } catch {
      setCheckoutPending(false);
      toast.error("Couldn't reach Stripe. Try again in a moment, or press Next to skip this stop.");
    }
  }, [state, userId]);

  const link = useMemo<TourChatLink>(
    () => ({ wantsDraft: touring && step.screen === "chat", register: setChat }),
    [touring, step.screen],
  );

  return (
    <TourChatLinkContext.Provider value={link}>
      {children}
      {me && <DemoBanner expiresAt={me.demo_expires_at} onRestartTour={() => dispatch({ type: "restart" })} />}
      {me && ready && state.phase !== "idle" && (
        <TourOverlay
          phase={state.phase}
          index={state.index}
          chat={chat}
          chatLimit={me.usage.limit}
          dispatch={dispatch}
          onOpenCheckout={openCheckout}
          checkoutPending={checkoutPending}
        />
      )}
      {me && ready && state.phase === "idle" && state.answered && <Hotspots onOpen={(index) => dispatch({ type: "tip", index })} />}
      {me && ready && resumeOffered && (
        <section className="tour-resume" aria-label="Resume the tour">
          <p>
            Back from Stripe. Pick the tour up at stop {UPGRADE_INDEX + 2} of {STEPS.length}?
          </p>
          <div className="tour-row">
            <Button
              size="sm"
              className="bg-bp-red text-white hover:bg-[#b80412]"
              onClick={() => {
                dispatchStore({ type: "close-resume" });
                dispatch({ type: "resume", index: UPGRADE_INDEX + 1 });
              }}
            >
              Continue the tour
            </Button>
            <Button size="sm" variant="secondary" onClick={() => dispatchStore({ type: "close-resume" })}>
              Not now
            </Button>
          </div>
        </section>
      )}
    </TourChatLinkContext.Provider>
  );
}
