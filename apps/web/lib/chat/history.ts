import type { ConversationSummary } from "@/lib/api/types";

export type HistoryGroup = { label: "Today" | "This week" | "Earlier"; items: ConversationSummary[] };

const DAY_MS = 24 * 60 * 60 * 1000;

function dayKey(date: Date, timeZone: string | undefined): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

export function groupConversations(
  conversations: readonly ConversationSummary[],
  now: Date,
  timeZone?: string,
): HistoryGroup[] {
  const today = dayKey(now, timeZone);
  const groups: HistoryGroup[] = [
    { label: "Today", items: [] },
    { label: "This week", items: [] },
    { label: "Earlier", items: [] },
  ];

  for (const conversation of conversations) {
    const updated = new Date(conversation.updated_at);
    if (dayKey(updated, timeZone) === today) groups[0].items.push(conversation);
    else if (now.getTime() - updated.getTime() < 7 * DAY_MS) groups[1].items.push(conversation);
    else groups[2].items.push(conversation);
  }
  return groups.filter((group) => group.items.length > 0);
}
