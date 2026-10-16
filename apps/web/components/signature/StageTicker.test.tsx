import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Stage } from "@/lib/agent-state";

import { StageTicker } from "./StageTicker";

const stages: Stage[] = [
  { name: "predict_match", status: "done", summary: "Ran the model for Bayern v Leipzig" },
  { name: "lookup_player", status: "failed", summary: "No player found for Kane2" },
  { name: "get_weather", status: "running", summary: null },
];

describe("StageTicker", () => {
  it("lists one line per stage with the server summary and the tool name", () => {
    render(<StageTicker stages={stages} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("Ran the model for Bayern v Leipzig")).toBeInTheDocument();
    expect(screen.getByText("predict_match")).toBeInTheDocument();
  });

  it("falls back to the caption while a stage has no summary yet", () => {
    render(<StageTicker stages={stages} />);
    expect(screen.getByText("Checking the weather")).toBeInTheDocument();
  });

  it("names unknown tools without inventing copy", () => {
    render(<StageTicker stages={[{ name: "check_referee", status: "running", summary: null }]} />);
    expect(screen.getByText("Working on it")).toBeInTheDocument();
    expect(screen.getByText("check_referee")).toBeInTheDocument();
  });

  it("marks stages by status for sighted and screen reader users", () => {
    render(<StageTicker stages={stages} />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.dataset.status)).toEqual(["done", "failed", "running"]);
    expect(items[0]).toHaveTextContent("✓");
    expect(items[1]).toHaveTextContent("!");
    expect(items[2]).toHaveTextContent("›");
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("summarises the count in the toggle", () => {
    render(<StageTicker stages={stages} />);
    expect(screen.getByText("3 agent steps")).toBeInTheDocument();
  });

  it("uses singular for one step", () => {
    render(<StageTicker stages={stages.slice(0, 1)} />);
    expect(screen.getByText("1 agent step")).toBeInTheDocument();
  });

  it("is open while the agent works and collapses when told to", () => {
    const { container, rerender } = render(<StageTicker stages={stages} />);
    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details.open).toBe(true);
    rerender(<StageTicker stages={stages} collapsed />);
    expect(details.open).toBe(false);
  });

  it("renders nothing without stages", () => {
    const { container } = render(<StageTicker stages={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
