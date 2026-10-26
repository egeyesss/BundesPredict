import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "./privacy/page";
import TermsPage from "./terms/page";

describe("demo lines in the legal pages", () => {
  it("terms say demo accounts and their data are deleted after 24 hours", () => {
    render(<TermsPage />);
    expect(screen.getByText(/demo accounts are throwaway accounts/i)).toHaveTextContent(/deleted after 24 hours/);
  });

  it("privacy says the same and discloses the hashed IP kept for up to two days", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/starting a demo keeps a one-way hash of your IP address for up to two days to limit abuse/i)).toBeInTheDocument();
    expect(screen.getAllByText(/deleted after 24 hours/i).length).toBeGreaterThanOrEqual(2);
  });
});
