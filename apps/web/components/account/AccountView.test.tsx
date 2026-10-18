import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { meFor } from "@/lib/api/mocks/data";

vi.mock("./SessionProvider", () => ({ useSession: () => ({ state: { status: "loading" }, refresh: vi.fn(), setMe: vi.fn() }) }));

import { AccountView } from "./AccountView";

describe("AccountView heading", () => {
  it("names the account by the part of the email before the @ when there is no name", () => {
    render(<AccountView initialMe={{ ...meFor("free"), name: null, email: "mp-qa-free@example.com" }} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("mp-qa-free");
    expect(screen.getAllByText("mp-qa-free@example.com")).toHaveLength(1);
  });

  it("uses the name when the account has one", () => {
    render(<AccountView initialMe={{ ...meFor("free"), name: "Sam Rivera" }} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sam Rivera");
  });
});
