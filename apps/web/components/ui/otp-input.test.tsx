import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { OtpInput, type OtpStatus } from "./otp-input";

function Harness({ onComplete = () => {}, status = "idle" as OtpStatus, length = 8 }) {
  const [value, setValue] = useState("");
  return (
    <>
      <OtpInput label="Sign-in code" length={length} value={value} onChange={setValue} onComplete={onComplete} status={status} separatorAfter={4} />
      <output data-testid="value">{value}</output>
    </>
  );
}

const slots = () => screen.getAllByRole("textbox");
const value = () => screen.getByTestId("value").textContent;

describe("OtpInput", () => {
  it("builds on its own last keystroke when the parent has not re-rendered yet", () => {
    const onChange = vi.fn();
    // The parent never passes the new value back, like a render still pending under load.
    render(<OtpInput label="Code" length={4} value="" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Character 1 of 4" }), { target: { value: "A" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Character 2 of 4" }), { target: { value: "B" } });
    expect(onChange).toHaveBeenLastCalledWith("AB");
  });

  it("renders one labelled slot per character in a group", () => {
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Sign-in code" })).toBeInTheDocument();
    expect(slots()).toHaveLength(8);
    expect(slots()[0]).toHaveAccessibleName("Character 1 of 8");
    expect(slots()[0]).toHaveAttribute("autocomplete", "one-time-code");
  });

  it("moves focus along as the user types and uppercases letters", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(slots()[0]);
    await user.keyboard("bcdf");
    expect(value()).toBe("BCDF");
    expect(slots()[4]).toHaveFocus();
  });

  it("ignores characters outside A to Z and 0 to 9", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(slots()[0]);
    await user.keyboard("a-!b");
    expect(value()).toBe("AB");
  });

  it("completes once, with the whole code, when the last slot fills", async () => {
    const onComplete = vi.fn();
    const user = userEvent.setup();
    render(<Harness onComplete={onComplete} />);
    await user.click(slots()[0]);
    await user.keyboard("BCDFGHJK");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("BCDFGHJK");
  });

  it("fills from a paste, dropping the dash allauth puts in the middle", async () => {
    const onComplete = vi.fn();
    const user = userEvent.setup();
    render(<Harness onComplete={onComplete} />);
    await user.click(slots()[0]);
    await user.paste("bcdf-ghjk");
    expect(value()).toBe("BCDFGHJK");
    expect(onComplete).toHaveBeenCalledWith("BCDFGHJK");
  });

  it("deletes backwards across slots", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(slots()[0]);
    await user.keyboard("BCD{Backspace}{Backspace}");
    expect(value()).toBe("B");
    expect(slots()[1]).toHaveFocus();
  });

  it("keeps the code contiguous when a later slot is clicked", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(slots()[0]);
    await user.keyboard("BC");
    await user.click(slots()[6]);
    expect(slots()[2]).toHaveFocus();
  });

  it("locks the slots while a code is being checked", async () => {
    const user = userEvent.setup();
    render(<Harness status="verifying" />);
    await user.click(slots()[0]);
    await user.keyboard("B");
    expect(value()).toBe("");
    expect(slots()[0]).toHaveAttribute("readonly");
  });

  it("exposes the error state to assistive tech", () => {
    render(<Harness status="error" />);
    expect(screen.getByRole("group", { name: "Sign-in code" })).toHaveAttribute("data-status", "error");
    expect(slots()[0]).toHaveAttribute("aria-invalid", "true");
  });
});
