import { describe, expect, it } from "vitest";

import type { ConversationSummary } from "@/lib/api/types";

import { groupConversations } from "./history";

const NOW = new Date("2026-10-16T15:00:00Z");

function chat(id: string, updated_at: string): ConversationSummary {
  return { id, title: id, fixture_id: null, updated_at };
}

describe("groupConversations", () => {
  it("sorts chats into today, this week and earlier by when they were last used", () => {
    const groups = groupConversations(
      [
        chat("a", "2026-10-16T09:00:00Z"),
        chat("b", "2026-10-14T18:00:00Z"),
        chat("c", "2026-10-02T18:00:00Z"),
      ],
      NOW,
      "UTC",
    );
    expect(groups.map((group) => [group.label, group.items.map((item) => item.id)])).toEqual([
      ["Today", ["a"]],
      ["This week", ["b"]],
      ["Earlier", ["c"]],
    ]);
  });

  it("leaves out groups with no chats", () => {
    expect(groupConversations([chat("a", "2026-10-16T09:00:00Z")], NOW, "UTC").map((group) => group.label)).toEqual(["Today"]);
    expect(groupConversations([], NOW, "UTC")).toEqual([]);
  });

  it("decides today in the viewer's timezone", () => {
    const lateEvening = chat("a", "2026-10-16T02:00:00Z");
    expect(groupConversations([lateEvening], NOW, "America/Toronto")[0].label).toBe("This week");
    expect(groupConversations([lateEvening], NOW, "UTC")[0].label).toBe("Today");
  });
});
