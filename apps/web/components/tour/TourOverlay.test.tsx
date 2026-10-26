import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReducer } from "react";

import type { TourChatHandle } from "./chat-link";
import { STEPS } from "./steps";
import { TourOverlay } from "./TourOverlay";
import { INITIAL_TOUR, tourReducer, type TourState } from "./tour-state";

function laidOut(element: HTMLElement, rect: { left: number; top: number; width: number; height: number }) {
  const box = { ...rect, right: rect.left + rect.width, bottom: rect.top + rect.height, x: rect.left, y: rect.top, toJSON: () => ({}) };
  element.getClientRects = () => [box] as unknown as DOMRectList;
  element.getBoundingClientRect = () => box as DOMRect;
}

const idleChat: TourChatHandle = { status: "empty", canSend: false, outOfChats: false, recorded: false, send: vi.fn(), replay: vi.fn() };

function Harness({ initial = INITIAL_TOUR, chat = null, onCheckout = async () => {} }: { initial?: TourState; chat?: TourChatHandle | null; onCheckout?: () => Promise<void> }) {
  const [state, dispatch] = useReducer(tourReducer, initial);
  return (
    <>
      <button type="button" onClick={() => dispatch({ type: "restart" })}>
        opener
      </button>
      <p data-testid="phase">{`${state.phase}:${state.index}:${state.completed}`}</p>
      {state.phase !== "idle" && (
        <TourOverlay phase={state.phase} index={state.index} chat={chat} chatLimit={10} dispatch={dispatch} onOpenCheckout={onCheckout} checkoutPending={false} />
      )}
    </>
  );
}

const anchors: HTMLElement[] = [];
function addAnchor(name: string, rect: { left: number; top: number; width: number; height: number }) {
  const anchor = document.createElement("div");
  anchor.dataset.tour = name;
  document.body.append(anchor);
  laidOut(anchor, rect);
  anchors.push(anchor);
  return anchor;
}

beforeEach(() => {
  window.scrollBy = vi.fn();
  Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 3000 });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, get: () => 360 });
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, get: () => 300 });
});
afterEach(() => {
  anchors.splice(0).forEach((anchor) => anchor.remove());
  Reflect.deleteProperty(document.documentElement, "scrollHeight");
  Reflect.deleteProperty(HTMLElement.prototype, "offsetWidth");
  Reflect.deleteProperty(HTMLElement.prototype, "offsetHeight");
  vi.useRealTimers();
});

describe("welcome card", () => {
  it("offers the tour or a look around, and a look around closes it", async () => {
    render(<Harness />);
    const dialog = await screen.findByRole("dialog", { name: "Take the tour" });
    expect(dialog).toHaveTextContent("Fifteen short stops");
    expect(screen.getByRole("button", { name: "Take the tour" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Look around first" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("phase")).toHaveTextContent("idle:0:false");
  });

  it("starts the tour at the first stop", async () => {
    render(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    const dialog = screen.getByRole("dialog", { name: STEPS[0].title });
    expect(dialog).toHaveTextContent("1 of 15 · Matchday");
    expect(dialog).toHaveTextContent("How it's measured");
    expect(dialog).toHaveTextContent(STEPS[0].what);
    expect(dialog).toHaveTextContent(STEPS[0].how);
  });
});

describe("the walk", () => {
  const begin = async () => {
    render(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
  };

  it("steps forward and back with the buttons and the arrow keys, naming the screen of each stop", async () => {
    await begin();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("2 of 15");
    await userEvent.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}");
    expect(screen.getByRole("dialog")).toHaveTextContent("5 of 15 · Chat");
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("dialog")).toHaveTextContent("4 of 15 · Matchday");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("3 of 15");
  });

  it("has no Back on the first stop and says Finish on the last", async () => {
    await begin();
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
    await userEvent.keyboard("{ArrowRight}".repeat(14));
    expect(screen.getByRole("dialog")).toHaveTextContent("15 of 15 · Admin");
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("phase")).toHaveTextContent("idle:14:true");
  });

  it("closes on Escape and on Skip tour, unfinished", async () => {
    await begin();
    await userEvent.keyboard("{ArrowRight}{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("phase")).toHaveTextContent("idle:1:false");
  });

  it("skips from the bubble", async () => {
    await begin();
    await userEvent.click(screen.getByRole("button", { name: "Skip tour" }));
    expect(screen.getByTestId("phase")).toHaveTextContent("idle:0:false");
  });

  it("keeps Tab inside the bubble in both directions", async () => {
    await begin();
    await userEvent.keyboard("{ArrowRight}");
    const skip = screen.getByRole("button", { name: "Skip tour" });
    const next = screen.getByRole("button", { name: "Next" });
    expect(next).toHaveFocus();
    await userEvent.tab();
    expect(skip).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(next).toHaveFocus();
  });

  it("pulls focus back in when it escapes behind the dim layer", async () => {
    await begin();
    act(() => screen.getByRole("button", { name: "opener" }).focus());
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toHaveFocus());
  });

  it("returns focus to the control that opened it", async () => {
    render(<Harness initial={{ ...INITIAL_TOUR, phase: "idle", answered: true }} />);
    const opener = screen.getByRole("button", { name: "opener" });
    await userEvent.click(opener);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(opener).toHaveFocus());
  });
});

describe("a single tip from a hotspot", () => {
  it("shows one stop with no counter, dots or Back, and Got it closes without touching progress", async () => {
    render(<Harness initial={{ phase: "tip", index: 7, answered: true, completed: true }} />);
    const dialog = await screen.findByRole("dialog", { name: STEPS[7].title });
    expect(dialog).toHaveTextContent("Quick tip");
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Skip tour" })).not.toBeInTheDocument();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("dialog")).toHaveTextContent("Quick tip");
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.getByTestId("phase")).toHaveTextContent("idle:7:true");
  });
});

describe("the spotlight", () => {
  it("sits on the anchor, follows it as it moves, and flips the bubble when it runs out of room", async () => {
    const anchor = addAnchor("fixture", { left: 100, top: 200, width: 300, height: 120 });
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 900 });

    render(<Harness initial={{ phase: "tour", index: 0, answered: true, completed: false }} />);
    const dialog = await screen.findByRole("dialog");
    const spot = document.querySelector<HTMLElement>(".tour-spot")!;
    await waitFor(() => expect(spot.style.left).toBe("92px"));
    expect(spot.style.top).toBe("192px");
    expect(spot.style.width).toBe("316px");
    expect(dialog.dataset.side).toBe("right");

    laidOut(anchor, { left: 1100, top: 300, width: 300, height: 120 });
    await waitFor(() => expect(spot.style.left).toBe("1092px"));
    expect(dialog.dataset.side).toBe("left");
    expect(window.scrollBy).not.toHaveBeenCalled();
  });

  it("scrolls an anchor that is off screen into view, but leaves one that is already visible", async () => {
    addAnchor("fixture", { left: 100, top: 1400, width: 300, height: 120 });
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 900 });
    render(<Harness initial={{ phase: "tour", index: 0, answered: true, completed: false }} />);
    await waitFor(() => expect(window.scrollBy).toHaveBeenCalled());
    const [{ top, behavior }] = vi.mocked(window.scrollBy).mock.calls[0] as unknown as [{ top: number; behavior: string }];
    expect(behavior).toBe("smooth");
    expect(1400 - top).toBeGreaterThanOrEqual(76 + 16);
    expect(1400 + 120 - top).toBeLessThanOrEqual(900 - 16);
  });

  it("docks the bubble as a sheet on a phone", async () => {
    addAnchor("fixture", { left: 16, top: 160, width: 343, height: 140 });
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 375 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 812 });

    render(<Harness initial={{ phase: "tour", index: 0, answered: true, completed: false }} />);
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog.dataset.side).toBe("sheet"));
    expect(dialog.style.bottom).toContain("12px");
    expect(dialog.style.top).toBe("auto");
  });

  it("says so, and still lets the visitor carry on, when the anchor never shows up", async () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance", "setTimeout", "clearTimeout"] });
    render(<Harness initial={{ phase: "tour", index: 2, answered: true, completed: false }} />);
    act(() => {
      vi.advanceTimersByTime(11_000);
    });
    expect(screen.getByRole("dialog")).toHaveTextContent("isn't showing right now");
    expect(screen.getByRole("dialog").dataset.side).toBe("center");
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });
});

describe("the chat stops", () => {
  const atMessage = { phase: "tour", index: 4, answered: true, completed: false } as const;

  it("offers to send the suggested message as one of the demo chats", async () => {
    const send = vi.fn();
    render(<Harness initial={atMessage} chat={{ ...idleChat, canSend: true, send }} />);
    await userEvent.click(await screen.findByRole("button", { name: "Send this message" }));
    expect(send).toHaveBeenCalledOnce();
    expect(screen.getByRole("dialog")).toHaveTextContent("Uses 1 of your 10 demo chats");
  });

  it("explains that a recording stands in when the demo chats are used up", async () => {
    render(<Harness initial={atMessage} chat={{ ...idleChat, outOfChats: true }} />);
    expect(await screen.findByRole("dialog")).toHaveTextContent("used all 10 demo chats");
  });

  it("labels a replay as a recording", async () => {
    render(<Harness initial={{ ...atMessage, index: 6 }} chat={{ ...idleChat, status: "done", recorded: true }} />);
    expect(await screen.findByRole("dialog")).toHaveTextContent("Recorded example.");
  });

  it("waits for a live answer, with a way to a recording", async () => {
    const replay = vi.fn();
    render(<Harness initial={{ ...atMessage, index: 6 }} chat={{ ...idleChat, status: "busy", replay }} />);
    await userEvent.click(await screen.findByRole("button", { name: "Show a recorded example instead" }));
    expect(replay).toHaveBeenCalledOnce();
  });

  it("opens the Stripe test checkout from the upgrade stop", async () => {
    const onCheckout = vi.fn().mockResolvedValue(undefined);
    render(<Harness initial={{ ...atMessage, index: 9 }} onCheckout={onCheckout} />);
    await userEvent.click(await screen.findByRole("button", { name: "Open the Stripe test checkout" }));
    expect(onCheckout).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });
});
