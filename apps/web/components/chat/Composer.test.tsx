import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Composer, type RateLimitState } from "./Composer";
import { LimitReached } from "./LimitReached";
import { QuotaMeter } from "./QuotaMeter";

const idleRate: RateLimitState = { active: false, finished: false, secondsLeft: 0 };
const usage = { used: 1, limit: 3, resets_at: "2026-10-16T00:00:00Z" };

function Harness(props: { onSend: () => void; busy?: boolean; rate?: RateLimitState; initial?: string }) {
  const [value, setValue] = useState(props.initial ?? "");
  return (
    <Composer
      value={value}
      onChange={setValue}
      onSend={props.onSend}
      busy={props.busy ?? false}
      placeholder="Tell the agent what changed"
      rateLimit={props.rate ?? idleRate}
      meter={<QuotaMeter plan="free" usage={usage} />}
    />
  );
}

describe("Composer", () => {
  it("sends on Enter and keeps Shift+Enter for new lines", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} initial="Kane is out" />);
    const box = screen.getByRole("textbox", { name: "Message" });
    await userEvent.type(box, "{Shift>}{Enter}{/Shift}");
    expect(onSend).not.toHaveBeenCalled();
    await userEvent.type(box, "{Enter}");
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("starts the message from a suggestion", async () => {
    render(<Harness onSend={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Lineups are out" }));
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("Lineups are out: ");
  });

  it("will not send an empty message or while the agent is busy", () => {
    const { rerender } = render(<Harness onSend={() => {}} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    rerender(<Harness onSend={() => {}} initial="Kane is out" busy />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("counts a rate limit down, disables Send, then says it is ready", () => {
    const { rerender } = render(<Harness onSend={() => {}} initial="Kane" rate={{ active: true, finished: false, secondsLeft: 7 }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Too many messages at once. You can send again in 7 s.");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    rerender(<Harness onSend={() => {}} initial="Kane" rate={{ active: false, finished: true, secondsLeft: 0 }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ready. You can send again.");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("limits a message to 500 characters, the API's maximum", () => {
    render(<Harness onSend={() => {}} />);
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute("maxlength", "500");
  });
});

describe("QuotaMeter", () => {
  it("shows one pip per chat with the spent ones dimmed, and the text", () => {
    const { container } = render(<QuotaMeter plan="free" usage={usage} />);
    expect(screen.getByText("2 of 3 free chats left today")).toBeInTheDocument();
    const pips = [...container.querySelectorAll("[data-pip]")];
    expect(pips).toHaveLength(3);
    expect(pips.map((pip) => pip.getAttribute("data-used"))).toEqual(["true", "false", "false"]);
  });

  it("shows fair use for pro with no pips", () => {
    const { container } = render(<QuotaMeter plan="pro" usage={{ ...usage, used: 12, limit: 100 }} />);
    expect(screen.getByText("Pro · fair use")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-pip]")).toHaveLength(0);
  });
});

describe("LimitReached", () => {
  it("tells a free user the reset time in their clock and offers the upgrade", () => {
    render(<LimitReached plan="free" usage={{ ...usage, used: 3 }} timeZone="America/Toronto" locale="en-US" />);
    const panel = screen.getByRole("status");
    expect(panel).toHaveTextContent("You've used today's 3 free chats.");
    expect(panel).toHaveTextContent("They reset at 8:00 PM your time.");
    expect(screen.getByRole("link", { name: /Upgrade to Pro/ })).toHaveAttribute("href", "/account");
    expect(screen.getByRole("link", { name: "Back to matchday" })).toHaveAttribute("href", "/matchday");
  });

  it("offers sign-up to a demo visitor instead of an upgrade", () => {
    render(<LimitReached plan="demo" usage={{ ...usage, used: 10, limit: 10 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("You've used all 10 demo chats.");
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/login");
  });
});
