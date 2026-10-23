import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import { describe, expect, it } from "vitest";

import { trackRecord } from "@/lib/api/mocks/data";
import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

import { TrackRecordTeaser } from "./TrackRecordTeaser";

setupApiMocks();

describe("TrackRecordTeaser", () => {
  it("always shows the backtest figures, before and without the live record", async () => {
    server.use(http.get("*/api/v1/track-record", () => HttpResponse.json({ code: "not_implemented", message: "x" }, { status: 501 })));
    render(<TrackRecordTeaser />);
    expect(screen.getByText("1,827")).toBeInTheDocument();
    expect(screen.getByText("0.2045")).toBeInTheDocument();
    expect(screen.getByText(/closing market 0\.1967/)).toBeInTheDocument();
  });

  it("shows the live record once the endpoint answers", async () => {
    render(<TrackRecordTeaser />);
    expect(await screen.findByText("63")).toBeInTheDocument();
    expect(screen.getByText("Live since 2026-08-28")).toBeInTheDocument();
    expect(screen.getByText(/bookmaker 0\.2012/)).toBeInTheDocument();
  });

  it("says the record is backtest only while no live match has been scored", async () => {
    server.use(
      http.get("*/api/v1/track-record", () =>
        HttpResponse.json({ ...trackRecord, live: { ...trackRecord.live, model: null, bookmaker: null } }),
      ),
    );
    render(<TrackRecordTeaser />);
    expect(await screen.findByText(/no live matches scored yet/i)).toBeInTheDocument();
    expect(screen.getByText(/backtest only/i)).toBeInTheDocument();
  });

  it("names the failure without hiding the backtest when the endpoint is down", async () => {
    server.use(http.get("*/api/v1/track-record", () => HttpResponse.json({ code: "unavailable", message: "x" }, { status: 503 })));
    render(<TrackRecordTeaser />);
    expect(await screen.findByText(/live record is unavailable right now/i)).toBeInTheDocument();
    expect(screen.getByText("1,827")).toBeInTheDocument();
  });

  it("links to the full track record", () => {
    render(<TrackRecordTeaser />);
    expect(screen.getByRole("link", { name: /full track record/i })).toHaveAttribute("href", "/track-record");
  });
});
