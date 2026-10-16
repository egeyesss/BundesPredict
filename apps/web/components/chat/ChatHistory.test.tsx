import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import { describe, expect, it } from "vitest";

import { conversationPage, notAuthenticated } from "@/lib/api/mocks/data";
import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

import { ChatHistoryProvider, useChatHistory } from "./ChatHistory";
import { HistoryList } from "./HistoryList";

setupApiMocks();

function renderList() {
  return render(
    <ChatHistoryProvider>
      <HistoryList />
      <Probe />
    </ChatHistoryProvider>,
  );
}

function Probe() {
  const history = useChatHistory();
  return (
    <>
      <button type="button" onClick={() => history.upsert({ id: "new-1", title: "Kane and the rain", fixture_id: null, updated_at: new Date().toISOString() })}>
        upsert
      </button>
      <span data-testid="nonce">{history.sessionNonce}</span>
    </>
  );
}

describe("HistoryList", () => {
  it("lists the saved conversations as links to their pages", async () => {
    renderList();
    const link = await screen.findByRole("link", { name: /Guirassy is out for Dortmund/ });
    expect(link).toHaveAttribute("href", `/chat/${conversationPage.results[0].id}`);
    expect(screen.getAllByRole("link", { name: /./ }).length).toBeGreaterThanOrEqual(4);
  });

  it("names the match under a chat that was about one, using this week's fixtures", async () => {
    renderList();
    const link = await screen.findByRole("link", { name: /Guirassy is out for Dortmund/ });
    await waitFor(() => expect(within(link).getByText("Dortmund v Hoffenheim")).toBeInTheDocument());
    expect(within(link).getAllByRole("img", { hidden: true }).length).toBe(2);
  });

  it("puts a chat started in this session at the top", async () => {
    renderList();
    await screen.findByRole("link", { name: /Guirassy/ });
    await userEvent.click(screen.getByRole("button", { name: "upsert" }));
    const links = screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/chat/"));
    expect(links[0]).toHaveAccessibleName(/Kane and the rain/);
  });

  it("starts a new chat by bumping the session", async () => {
    renderList();
    await screen.findByRole("link", { name: /Guirassy/ });
    await userEvent.click(screen.getByRole("link", { name: "New chat" }));
    expect(screen.getByTestId("nonce")).toHaveTextContent("1");
  });

  it("shows an empty state that points at the matchday", async () => {
    server.use(http.get("*/api/v1/conversations", () => HttpResponse.json({ next: null, results: [] })));
    renderList();
    expect(await screen.findByText("No chats yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to matchday" })).toHaveAttribute("href", "/matchday");
  });

  it("says what broke and retries", async () => {
    server.use(http.get("*/api/v1/conversations", () => HttpResponse.json({ code: "server_error", message: "Boom." }, { status: 500 }), { once: true }));
    renderList();
    expect(await screen.findByText("Couldn't load your chats")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: /Guirassy/ })).toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in", async () => {
    server.use(http.get("*/api/v1/conversations", () => HttpResponse.json(notAuthenticated, { status: 401 })));
    renderList();
    expect(await screen.findByText("Sign in to keep your chats")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  it("loads older chats when the list has another page", async () => {
    server.use(
      http.get("*/api/v1/conversations", ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        return cursor
          ? HttpResponse.json({ next: null, results: [{ id: "old-1", title: "An old chat", fixture_id: null, updated_at: "2026-08-01T10:00:00Z" }] })
          : HttpResponse.json({ next: "page-2", results: conversationPage.results });
      }),
    );
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Show older chats" }));
    expect(await screen.findByRole("link", { name: /An old chat/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show older chats" })).not.toBeInTheDocument();
  });
});
