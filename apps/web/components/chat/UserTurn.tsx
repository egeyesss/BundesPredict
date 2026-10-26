import type { UserTurn as Turn } from "@/lib/chat/transcript";

export function UserTurn({ turn }: { turn: Turn }) {
  return (
    <div data-tour="message" className="mx-auto flex w-full max-w-[760px] justify-end">
      <p className="max-w-[80%] rounded-[12px_12px_4px_12px] border border-bp-border bg-bp-surface-2 px-3.5 py-2.5 break-words whitespace-pre-wrap">
        {turn.text}
      </p>
    </div>
  );
}
