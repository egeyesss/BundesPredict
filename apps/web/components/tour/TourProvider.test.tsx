import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import { useEffect, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/components/account/SessionProvider";
import { fixtureCards } from "@/lib/api/mocks/data";
import { server } from "@/lib/api/mocks/node";
import { setMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";
import { groupByMatchday } from "@/lib/matchday";

const nav = vi.hoisted(() => ({ pathname: "/matchday", push: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname, useRouter: () => ({ push: nav.push }) }));
const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));

import { useTourChatLink, type TourChatHandle } from "./chat-link";
import { markCheckoutStarted } from "./tour-storage";
import { TourProvider } from "./TourProvider";

setupApiMocks();

const firstCardId = groupByMatchday(fixtureCards)[0].fixtures[0].id;

function laidOut(element: HTMLElement) {
  const box = { left: 100, top: 300, width: 200, height: 80, right: 300, bottom: 380, x: 100, y: 300, toJSON: () => ({}) };
  element.getClientRects = () => [box] as unknown as DOMRectList;
  element.getBoundingClientRect = () => box as DOMRect;
}

function Anchor({ name }: { name: string }) {
  return (
    <div
      data-tour={name}
      ref={(element) => {
        if (element) laidOut(element);
      }}
    />
  );
}

function mount(children: ReactNode = <Anchor name="fixture" />) {
  return render(
    <SessionProvider>
      <TourProvider>{children}</TourProvider>
    </SessionProvider>,
  );
}

beforeEach(() => {
  nav.pathname = "/matchday";
  nav.push.mockReset();
  navigate.mockReset();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/matchday");
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

describe("who gets the demo layer", () => {
  it("leaves a regular signed-in user's page alone", async () => {
    setMockSession("free");
    mount(<p>page</p>);
    await screen.findByText("page");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("region", { name: "Demo mode" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows a demo user the banner and the welcome card on the first visit", async () => {
    setMockSession("demo");
    mount();
    expect(await screen.findByRole("dialog", { name: "Take the tour" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Demo mode" })).toHaveTextContent("nothing is charged");
    expect(document.querySelector("[data-tour-hotspots]")).toBeNull();
  });
});

describe("persistence", () => {
  it("remembers the stop across a reload and the answered welcome card", async () => {
    setMockSession("demo");
    const first = mount();
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    expect(screen.getByRole("dialog")).toHaveTextContent("3 of 15");
    first.unmount();

    mount();
    expect(await screen.findByRole("dialog")).toHaveTextContent("3 of 15");
  });

  it("does not show the welcome card again once it was answered", async () => {
    setMockSession("demo");
    const first = mount();
    await userEvent.click(await screen.findByRole("button", { name: "Look around first" }));
    first.unmount();

    mount();
    await screen.findByRole("region", { name: "Demo mode" });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps working from memory when storage throws", async () => {
    setMockSession("demo");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("dialog")).toHaveTextContent("2 of 15");
  });

  it("keeps each demo account's tour separate", async () => {
    window.sessionStorage.setItem("bp-tour:999", JSON.stringify({ phase: "tour", index: 8, answered: true, completed: false }));
    setMockSession("demo");
    mount();
    expect(await screen.findByRole("dialog", { name: "Take the tour" })).toBeInTheDocument();
  });
});

describe("route hand-off", () => {
  const startTour = async () => {
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
  };

  it("pushes the chat page, pinned to the first matchday card's fixture, when Next leaves the matchday", async () => {
    setMockSession("demo");
    await startTour();
    await userEvent.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}");
    expect(nav.push).not.toHaveBeenCalled();
    await userEvent.keyboard("{ArrowRight}");
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(`/chat?fixture=${firstCardId}`));
    expect(nav.push).toHaveBeenCalledTimes(1);
  });

  it("goes back to the matchday from the first chat stop, and on to the other screens in turn", async () => {
    setMockSession("demo");
    await startTour();
    await userEvent.keyboard("{ArrowRight}".repeat(4));
    await waitFor(() => expect(nav.push).toHaveBeenCalledTimes(1));
    nav.pathname = "/chat";
    await userEvent.keyboard("{ArrowLeft}");
    await waitFor(() => expect(nav.push).toHaveBeenLastCalledWith("/matchday"));
    nav.pathname = "/matchday";
    await userEvent.keyboard("{ArrowRight}");
    await waitFor(() => expect(nav.push).toHaveBeenLastCalledWith(`/chat?fixture=${firstCardId}`));
    nav.pathname = "/chat";
    await userEvent.keyboard("{ArrowRight}".repeat(6));
    await waitFor(() => expect(nav.push).toHaveBeenLastCalledWith("/track-record"));
    nav.pathname = "/track-record";
    await userEvent.keyboard("{ArrowRight}".repeat(2));
    await waitFor(() => expect(nav.push).toHaveBeenLastCalledWith("/admin"));
  });

  it("still goes to the chat when the fixtures cannot be loaded", async () => {
    server.use(http.get("*/api/v1/fixtures", () => HttpResponse.json({ code: "x", message: "x" }, { status: 500 })));
    setMockSession("demo");
    await startTour();
    await userEvent.keyboard("{ArrowRight}".repeat(4));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/chat"));
  });

  it("starting from another screen sends the visitor to the first stop", async () => {
    setMockSession("demo");
    nav.pathname = "/admin";
    mount(<p>admin</p>);
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/matchday"));
  });
});

describe("hotspots after the tour", () => {
  it("puts a ? on every anchored element of the page, each opening only its own stop", async () => {
    setMockSession("demo");
    mount(
      <>
        <Anchor name="fixture" />
        <Anchor name="bar" />
      </>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Look around first" }));
    const fixture = await screen.findByRole("button", { name: "Explain: One card per fixture" });
    expect(screen.getByRole("button", { name: "Explain: Win, draw, loss odds" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Explain: How accurate/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Explain: Expected goals/ })).not.toBeInTheDocument();

    await userEvent.click(fixture);
    expect(screen.getByRole("dialog", { name: "One card per fixture" })).toHaveTextContent("Quick tip");
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Explain: One card per fixture" })).toHaveFocus());
  });

  it("stay after the tour is finished or skipped, and the banner's ? restarts it", async () => {
    setMockSession("demo");
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{Escape}");
    await screen.findByRole("button", { name: "Explain: One card per fixture" });

    await userEvent.click(screen.getByRole("button", { name: "Restart the tour" }));
    expect(await screen.findByRole("dialog", { name: "Take the tour" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Explain:/ })).not.toBeInTheDocument();
  });
});

describe("chat stops", () => {
  function FakeChat({ handle }: { handle: TourChatHandle }) {
    const link = useTourChatLink();
    const register = link?.register;
    useEffect(() => {
      register?.(handle);
      return () => register?.(null);
    }, [register, handle]);
    return <p data-testid="wants-draft">{String(link?.wantsDraft)}</p>;
  }

  const handle = (over: Partial<TourChatHandle> = {}): TourChatHandle => ({
    status: "empty",
    canSend: false,
    outOfChats: false,
    recorded: false,
    send: vi.fn(),
    replay: vi.fn(),
    ...over,
  });

  it("asks for the suggested message only while a chat stop is showing", async () => {
    setMockSession("demo");
    nav.pathname = "/chat";
    window.history.replaceState({}, "", "/chat");
    mount(<FakeChat handle={handle()} />);
    expect(await screen.findByTestId("wants-draft")).toHaveTextContent("false");
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{ArrowRight}".repeat(4));
    await waitFor(() => expect(screen.getByTestId("wants-draft")).toHaveTextContent("true"));
  });

  it("plays the recording once when the agent's steps are next and there is no answer", async () => {
    setMockSession("demo");
    nav.pathname = "/chat";
    const chat = handle();
    const view = mount(<FakeChat handle={chat} />);
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{ArrowRight}".repeat(4));
    expect(chat.replay).not.toHaveBeenCalled();
    await userEvent.keyboard("{ArrowRight}");
    await waitFor(() => expect(chat.replay).toHaveBeenCalledTimes(1));

    const playing = handle({ status: "busy", recorded: true });
    view.rerender(
      <SessionProvider>
        <TourProvider>
          <FakeChat handle={playing} />
        </TourProvider>
      </SessionProvider>,
    );
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    expect(playing.replay).not.toHaveBeenCalled();
    expect(chat.replay).toHaveBeenCalledTimes(1);
  });

  it("falls back to the recording when the live answer failed, but not while one is on its way", async () => {
    setMockSession("demo");
    nav.pathname = "/chat";
    const busy = handle({ status: "busy" });
    const view = mount(<FakeChat handle={busy} />);
    await userEvent.click(await screen.findByRole("button", { name: "Take the tour" }));
    await userEvent.keyboard("{ArrowRight}".repeat(5));
    expect(busy.replay).not.toHaveBeenCalled();

    const failed = handle({ status: "failed" });
    view.rerender(
      <SessionProvider>
        <TourProvider>
          <FakeChat handle={failed} />
        </TourProvider>
      </SessionProvider>,
    );
    await waitFor(() => expect(failed.replay).toHaveBeenCalledTimes(1));
  });
});

describe("coming back from Stripe", () => {
  it("offers to resume at the stop after the upgrade, only after a checkout this tour started", async () => {
    setMockSession("demo");
    nav.pathname = "/account";
    window.history.replaceState({}, "", "/account?checkout=success");
    markCheckoutStarted(102);
    window.sessionStorage.setItem("bp-tour:102", JSON.stringify({ phase: "idle", index: 9, answered: true, completed: false }));
    mount(<p>checked out</p>);

    const offer = await screen.findByRole("region", { name: "Resume the tour" });
    expect(offer).toHaveTextContent("stop 11 of 15");
    await userEvent.click(screen.getByRole("button", { name: "Continue the tour" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("11 of 15 · Track record");
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/track-record"));
  });

  it("stays quiet on the checkout return page when no checkout was started from the tour", async () => {
    setMockSession("demo");
    nav.pathname = "/account";
    window.history.replaceState({}, "", "/account?checkout=success");
    window.sessionStorage.setItem("bp-tour:102", JSON.stringify({ phase: "idle", index: 9, answered: true, completed: false }));
    mount(<p>checked out</p>);
    await screen.findByRole("region", { name: "Demo mode" });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("region", { name: "Resume the tour" })).not.toBeInTheDocument();
  });

  it("opens the checkout from the upgrade stop, leaves the tour paused, and remembers to offer the resume", async () => {
    setMockSession("demo");
    window.sessionStorage.setItem("bp-tour:102", JSON.stringify({ phase: "tour", index: 9, answered: true, completed: false }));
    nav.pathname = "/chat";
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Open the Stripe test checkout" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith(expect.stringMatching(/^https:\/\//)));
    expect(JSON.parse(window.sessionStorage.getItem("bp-tour:102")!)).toMatchObject({ phase: "idle", index: 9 });
    expect(window.sessionStorage.getItem("bp-tour-checkout:102")).toBe("1");
  });
});

