import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FAQ_ENTRIES } from "./faq-content";
import { Faq } from "./Faq";

const question = (id: string) => screen.getByRole("button", { name: FAQ_ENTRIES.find((entry) => entry.id === id)!.question });

describe("Faq", () => {
  it("opens the first question's answer in the server markup", () => {
    render(<Faq />);
    expect(question("advice")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: question("advice").textContent! })).toHaveTextContent("analytics project");
  });

  it("keeps one answer open at a time", async () => {
    const user = userEvent.setup();
    render(<Faq />);
    await user.click(question("source"));
    expect(question("source")).toHaveAttribute("aria-expanded", "true");
    expect(question("advice")).toHaveAttribute("aria-expanded", "false");
    await waitFor(() => expect(screen.getAllByRole("region")).toHaveLength(1));
  });

  it("closes the open answer when its question is clicked again", async () => {
    const user = userEvent.setup();
    render(<Faq />);
    await user.click(question("advice"));
    expect(question("advice")).toHaveAttribute("aria-expanded", "false");
    await waitFor(() => expect(screen.queryAllByRole("region")).toHaveLength(0));
  });

  it("moves between questions with the arrow keys, Home and End", async () => {
    const user = userEvent.setup();
    render(<Faq />);
    question("advice").focus();
    await user.keyboard("{ArrowDown}");
    expect(question("source")).toHaveFocus();
    await user.keyboard("{End}");
    expect(question(FAQ_ENTRIES.at(-1)!.id)).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(question("advice")).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(question(FAQ_ENTRIES.at(-1)!.id)).toHaveFocus();
    await user.keyboard("{Home}");
    expect(question("advice")).toHaveFocus();
  });
});
