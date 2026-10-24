import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { newsEdgeEmpty, trackRecord } from "@/lib/api/mocks/data";
import type { TrackRecord } from "@/lib/api/types";

import { TrackRecordView } from "./TrackRecordView";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const emptyLive: TrackRecord = {
  ...trackRecord,
  live: { ...trackRecord.live, since: "2026-10-22", label: "Live since 2026-10-22", model: null, bookmaker: null, base_rate: null },
  matchdays: [],
  calibration: [],
};

describe("TrackRecordView with a scored season", () => {
  it("shows the live numbers next to the closing market and the base rate", () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);

    const rps = screen.getByText("Model RPS").closest("div")!;
    expect(within(rps).getByText("0.2086")).toBeInTheDocument();
    expect(within(rps).getByText("0.2012")).toBeInTheDocument();
    expect(within(rps).getByText("0.2304")).toBeInTheDocument();
    expect(screen.getByText("Live since 28 Aug 2026")).toBeInTheDocument();
  });

  it("flags a short record", () => {
    const short = { ...trackRecord, live: { ...trackRecord.live, model: { n_fixtures: 12, rps: 0.2, log_loss: 1, hit_rate: 0.5 } } };
    render(<TrackRecordView outcome={{ status: "ok", record: short }} />);

    expect(screen.getByText(/Only 12 matches scored/)).toBeInTheDocument();
  });

  it("does not call 63 matches a short record", () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);

    expect(screen.queryByText(/matches scored so far/)).not.toBeInTheDocument();
  });

  it("lists every scored match under its matchday, latest open", () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);

    const latest = screen.getByText("Matchday 7").closest("details")!;
    expect(latest).toHaveAttribute("open");
    expect(within(latest).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("Matchday 6").closest("details")).not.toHaveAttribute("open");
    expect(within(latest).getByLabelText("Final score 5 to 1")).toBeInTheDocument();
  });

  it("swaps a chart for its table and back", async () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);
    const card = screen.getByRole("region", { name: "Average RPS per matchday" });

    await userEvent.click(within(card).getByRole("button", { name: "Show as table" }));

    expect(within(card).getByRole("table")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Hide table" })).toBeInTheDocument();
    expect(within(card).getAllByRole("row")).toHaveLength(8);
  });

  it("labels the backtest apart from the live record", async () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);

    await userEvent.click(screen.getByRole("tab", { name: "Backtest · 5 seasons" }));

    const panel = screen.getByRole("tabpanel", { name: "Backtest · 5 seasons" });
    expect(within(panel).getByText("1,827")).toBeInTheDocument();
    expect(within(panel).getByText("0.2045")).toBeInTheDocument();
    expect(within(panel).getByText("0.0105")).toBeInTheDocument();
  });

  it("moves between the tabs with the arrow keys", async () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);
    screen.getByRole("tab", { name: "This season" }).focus();

    await userEvent.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Backtest · 5 seasons" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("TrackRecordView before anything is scored", () => {
  it("says so honestly and points at the backtest", async () => {
    render(<TrackRecordView outcome={{ status: "ok", record: emptyLive }} />);

    expect(screen.getByRole("heading", { name: "No matchday scored yet" })).toBeInTheDocument();
    expect(screen.getByText("Live since 22 Oct 2026")).toBeInTheDocument();
    expect(screen.queryByText("Model RPS")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "See the backtest" }));

    expect(screen.getByRole("tab", { name: "Backtest · 5 seasons" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("TrackRecordView when the API fails", () => {
  it("names what broke and offers a retry", () => {
    render(<TrackRecordView outcome={{ status: "error" }} />);

    expect(screen.getByRole("heading", { name: "Couldn't load the track record" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/ })).toBeInTheDocument();
  });
});

describe("news edge tracker", () => {
  it("lists every logged chat with its verdict and shows no rate under 20 compared", () => {
    render(<TrackRecordView outcome={{ status: "ok", record: trackRecord }} />);

    const tracker = screen.getByRole("region", { name: "News edge tracker" });
    expect(within(tracker).getAllByRole("listitem")).toHaveLength(3);
    expect(within(tracker).getByLabelText(/Borussia Dortmund win: opening 66%, agent 70%, closing 69%, ahead of the market/)).toBeInTheDocument();
    expect(within(tracker).getByLabelText(/Bayern Munich win: agent 80%, waiting for the closing line/)).toBeInTheDocument();
    expect(within(tracker).getByText(/No rate until 20 are compared \(18 to go\)/)).toBeInTheDocument();
    expect(within(tracker).queryByText(/% \)/)).not.toBeInTheDocument();
  });

  it("shows the rate once enough chats are compared", () => {
    const record = { ...trackRecord, news_edge: { ...trackRecord.news_edge, n_compared: 20, n_ahead: 9, rate: 0.45 } };
    render(<TrackRecordView outcome={{ status: "ok", record }} />);

    expect(screen.getByText("Ahead of the market in 9 of 20 compared chats (45%)")).toBeInTheDocument();
  });

  it("has an honest empty state with no example rows", () => {
    render(<TrackRecordView outcome={{ status: "ok", record: { ...trackRecord, news_edge: newsEdgeEmpty } }} />);

    const tracker = screen.getByRole("region", { name: "News edge tracker" });
    expect(within(tracker).getByText("No chats logged yet this season")).toBeInTheDocument();
    expect(within(tracker).queryByRole("listitem")).not.toBeInTheDocument();
  });
});
