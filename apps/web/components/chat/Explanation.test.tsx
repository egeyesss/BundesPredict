import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Explanation, closeOpenEmphasis } from "./Explanation";

describe("Explanation", () => {
  it("renders bold text and paragraphs instead of the raw markdown", () => {
    const { container } = render(<Explanation text={"**Stuttgart drop to 63%.** Their attack loses 0.35 xG.\n\nThe draw gains ground."} />);

    expect(screen.getByText("Stuttgart drop to 63%.").tagName).toBe("STRONG");
    expect(container.querySelectorAll("p")).toHaveLength(2);
    expect(container).not.toHaveTextContent("**");
  });

  it("renders a numbered list when the agent asks for details", () => {
    render(<Explanation text={"Which match?\n\n1. **Which team(s)** play\n2. **Which news** do you have"} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("does not turn raw html in the answer into elements", () => {
    const { container } = render(<Explanation text={'Fine <img src=x onerror="alert(1)"> done'} />);

    expect(container.querySelector("img")).toBeNull();
  });
});

describe("closeOpenEmphasis", () => {
  it("closes a bold run that is still being typed", () => {
    expect(closeOpenEmphasis("**The striker inj")).toBe("**The striker inj**");
  });

  it("leaves balanced text alone", () => {
    expect(closeOpenEmphasis("**Done.** Then more")).toBe("**Done.** Then more");
  });

  it("drops a lone marker that has no text after it yet", () => {
    expect(closeOpenEmphasis("Fine. **")).toBe("Fine. ");
    expect(closeOpenEmphasis("Fine. *")).toBe("Fine. ");
  });

  it("closes an open single-asterisk run", () => {
    expect(closeOpenEmphasis("*half")).toBe("*half*");
  });
});
