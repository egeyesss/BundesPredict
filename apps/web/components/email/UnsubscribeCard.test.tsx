import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import { describe, expect, it } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

import { UnsubscribeCard } from "./UnsubscribeCard";

setupApiMocks();

describe("UnsubscribeCard", () => {
  it("asks before changing anything", () => {
    render(<UnsubscribeCard token="signed" />);

    expect(screen.getByRole("heading", { name: "Stop the Thursday matchday email?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unsubscribe" })).toBeEnabled();
  });

  it("confirms after the request succeeds and points at the account page", async () => {
    render(<UnsubscribeCard token="signed" />);

    await userEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));

    expect(await screen.findByRole("heading", { name: "You're unsubscribed" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account settings" })).toHaveAttribute("href", "/account");
    expect(screen.queryByRole("button", { name: "Unsubscribe" })).not.toBeInTheDocument();
  });

  it("sends the token from the link", async () => {
    let received: unknown;
    server.use(
      http.post("*/api/v1/email/unsubscribe", async ({ request }) => {
        received = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(<UnsubscribeCard token="abc:def" />);

    await userEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));
    await screen.findByRole("heading", { name: "You're unsubscribed" });

    expect(received).toEqual({ token: "abc:def" });
  });

  it("says the link is not valid and offers the account page instead", async () => {
    render(<UnsubscribeCard token="invalid-link" />);

    await userEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));

    expect(await screen.findByRole("heading", { name: "This link doesn't work" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account settings" })).toHaveAttribute("href", "/account");
  });

  it("keeps the button for another try after a network failure", async () => {
    server.use(http.post("*/api/v1/email/unsubscribe", () => HttpResponse.error()));
    render(<UnsubscribeCard token="signed" />);

    await userEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach BundesPredict");
    expect(screen.getByRole("button", { name: "Unsubscribe" })).toBeEnabled();
  });

  it("explains an incomplete link without a button", () => {
    render(<UnsubscribeCard token={null} />);

    expect(screen.getByRole("heading", { name: "This link doesn't work" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unsubscribe" })).not.toBeInTheDocument();
  });
});
