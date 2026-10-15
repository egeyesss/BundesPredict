import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IslandActivityProvider, useIslandActivity } from "./IslandActivity";
import { IslandNav } from "./IslandNav";
import type { NavUser } from "./nav";

vi.mock("next/navigation", () => ({ usePathname: () => "/matchday" }));

const freeUser: NavUser = {
  name: "Ege",
  email: "ege@example.com",
  plan: "free",
  chatsUsed: 1,
  chatsLimit: 3,
};

function setViewport(width: number, scrollY = 0) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "scrollY", { configurable: true, value: scrollY });
}

function scrollTo(scrollY: number) {
  setViewport(window.innerWidth, scrollY);
  fireEvent.scroll(window);
}

function renderIsland(user: NavUser | null = null) {
  return render(
    <IslandActivityProvider>
      <IslandNav wordmark={<span data-testid="wordmark">BundesPredict</span>} user={user} />
    </IslandActivityProvider>,
  );
}

const island = () => screen.getByRole("navigation", { name: "Main", hidden: true });

describe("IslandNav", () => {
  beforeEach(() => setViewport(1440, 0));

  it("is full at the top of a wide page and fades in once measured", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    expect(island()).toHaveAttribute("data-mode", "full");
  });

  it("compacts when scrolled and expands again on hover", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    scrollTo(400);
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "compact"));

    await userEvent.hover(island());
    expect(island()).toHaveAttribute("data-mode", "full");
    await userEvent.unhover(island());
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "compact"), { timeout: 1000 });
  });

  it("expands a compact island when a link inside it takes keyboard focus", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    scrollTo(400);
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "compact"));
    await userEvent.tab();
    expect(island()).toHaveAttribute("data-mode", "full");
    // The focused control moves to the full layer instead of vanishing with the inert compact layer.
    const full = island().querySelector<HTMLElement>('[data-layer="full"]')!;
    expect(full).toContainElement(document.activeElement as HTMLElement);
  });

  it("only the active layer is exposed to assistive tech and the tab order", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    const layers = island().querySelectorAll<HTMLElement>("[data-layer]");
    expect(layers).toHaveLength(4);
    for (const layer of layers) {
      const active = layer.dataset.layer === "full";
      expect(layer.hasAttribute("inert")).toBe(!active);
      expect(layer).toHaveAttribute("aria-hidden", String(!active));
    }
  });

  it("renders the wordmark slot in every layer", () => {
    renderIsland();
    expect(screen.getAllByTestId("wordmark", { exact: true })).toHaveLength(4);
  });

  it("offers Sign in and Try the demo when signed out", async () => {
    renderIsland(null);
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    const full = within(island().querySelector<HTMLElement>('[data-layer="full"]')!);
    expect(full.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(full.getByRole("link", { name: "Try the demo" })).toBeInTheDocument();
  });

  it("shows the plan pill and account button when signed in", async () => {
    renderIsland(freeUser);
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    const full = within(island().querySelector<HTMLElement>('[data-layer="full"]')!);
    expect(full.getByText("Free")).toBeInTheDocument();
    expect(full.getByRole("button", { name: "Account menu" })).toBeInTheDocument();
    expect(full.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });

  it("marks the current page in the full layer", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    const full = within(island().querySelector<HTMLElement>('[data-layer="full"]')!);
    expect(full.getByRole("link", { name: "Matchday" })).toHaveAttribute("aria-current", "page");
    expect(full.getByRole("link", { name: "Chat" })).not.toHaveAttribute("aria-current");
  });

  it("shows the current page in the compact live activity", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-ready", "true"));
    const compact = island().querySelector<HTMLElement>('[data-layer="compact"]')!;
    expect(compact).toHaveTextContent("Matchday");
  });

  it("shows the agent caption instead while the agent runs", async () => {
    function StartAgent() {
      const { setAgentCaption } = useIslandActivity();
      return <button onClick={() => setAgentCaption("Running the model")}>start</button>;
    }
    render(
      <IslandActivityProvider>
        <IslandNav wordmark="x" user={null} />
        <StartAgent />
      </IslandActivityProvider>,
    );
    await userEvent.click(screen.getByText("start"));
    const compact = island().querySelector<HTMLElement>('[data-layer="compact"]')!;
    expect(compact).toHaveTextContent("Agent · Running the model");
  });
});

describe("IslandNav on a phone", () => {
  beforeEach(() => setViewport(375, 0));

  const menuButton = () => screen.getByRole("button", { name: "Open menu", hidden: true });
  const closeButton = () => screen.getByRole("button", { name: "Close menu", hidden: true });

  it("uses the mobile layout whatever the scroll position", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    scrollTo(900);
    expect(island()).toHaveAttribute("data-mode", "mobile");
  });

  it("opens the menu panel and focuses the close button without scrolling", async () => {
    renderIsland(freeUser);
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    const focusSpy = vi.spyOn(HTMLElement.prototype, "focus");
    await userEvent.click(menuButton());
    expect(island()).toHaveAttribute("data-mode", "open");
    expect(menuButton()).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(closeButton()).toHaveFocus());
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    focusSpy.mockRestore();
  });

  it("lists the account summary and four pages when signed in", async () => {
    renderIsland(freeUser);
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    await userEvent.click(menuButton());
    const menu = within(island().querySelector<HTMLElement>('[data-layer="open"]')!);
    expect(menu.getByText("ege@example.com")).toBeInTheDocument();
    expect(menu.getByText("2 of 3 free chats left today")).toBeInTheDocument();
    for (const page of ["Matchday", "Chat", "Track record", "Account"]) {
      expect(menu.getByRole("link", { name: new RegExp(`^${page}`) })).toBeInTheDocument();
    }
    expect(menu.getByRole("link", { name: "Upgrade to Pro" })).toBeInTheDocument();
    expect(menu.getByRole("link", { name: "Sign out" })).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the menu button", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    await userEvent.click(menuButton());
    await userEvent.keyboard("{Escape}");
    expect(island()).toHaveAttribute("data-mode", "mobile");
    await waitFor(() => expect(menuButton()).toHaveFocus());
  });

  it("closes when the scrim is clicked", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    await userEvent.click(menuButton());
    const scrim = document.querySelector<HTMLElement>("[data-island-scrim]")!;
    expect(scrim).toBeVisible();
    await userEvent.click(scrim);
    expect(island()).toHaveAttribute("data-mode", "mobile");
  });

  it("closes when a page is chosen", async () => {
    renderIsland();
    await waitFor(() => expect(island()).toHaveAttribute("data-mode", "mobile"));
    await userEvent.click(menuButton());
    const menu = within(island().querySelector<HTMLElement>('[data-layer="open"]')!);
    await act(async () => fireEvent.click(menu.getByRole("link", { name: /^Track record/ })));
    expect(island()).toHaveAttribute("data-mode", "mobile");
  });
});

describe("IslandNav preview", () => {
  it("renders inline in a forced mode for the styleguide", () => {
    render(<IslandNav wordmark="x" user={null} preview={{ mode: "open", label: "Island preview, open" }} />);
    const preview = screen.getByRole("group", { name: "Island preview, open" });
    expect(preview).toHaveAttribute("data-mode", "open");
    expect(preview).toHaveAttribute("data-ready", "true");
    expect(preview.closest("[data-island-wrap]")).toHaveAttribute("data-preview", "true");
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });
});
