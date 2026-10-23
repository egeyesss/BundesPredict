import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { meFor } from "@/lib/api/mocks/data";

import { EmailCard } from "./EmailCard";

describe("EmailCard", () => {
  it("says the email is for Pro plans and how to stop it", () => {
    render(<EmailCard me={meFor("free")} onSaved={() => {}} />);

    expect(screen.getByText(/Pro plan/)).toBeInTheDocument();
    expect(screen.getByText(/one-click unsubscribe/)).toBeInTheDocument();
  });
});
