"use client";

import { SendHorizontal } from "lucide-react";
import { useId, useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";

import { Banner } from "@/components/states/Banner";
import { Button } from "@/components/ui/button";

export const MAX_QUERY_LENGTH = 500;
const MAX_HEIGHT_PX = 140;

const SUGGESTIONS = [
  { label: "Lineups are out", prefix: "Lineups are out: " },
  { label: "Injury news", prefix: "Injury news: " },
  { label: "Weather at kickoff", prefix: "Weather at kickoff: " },
] as const;

export type RateLimitState = { active: boolean; finished: boolean; secondsLeft: number };

type ComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  busy: boolean;
  placeholder: string;
  rateLimit: RateLimitState;
  meter: ReactNode;
};

export function Composer({ value, onChange, onSend, busy, placeholder, rateLimit, meter }: ComposerProps) {
  const inputId = useId();
  const textarea = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim() !== "" && !busy && !rateLimit.active;

  useLayoutEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(MAX_HEIGHT_PX, element.scrollHeight)}px`;
  }, [value, placeholder]);

  function submit() {
    if (canSend) onSend();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="mx-auto grid w-full max-w-[760px] gap-2.5"
    >
      {(rateLimit.active || rateLimit.finished) && (
        <Banner tone={rateLimit.active ? "warn" : "info"} icon={rateLimit.active ? "!" : "✓"} role="alert">
          {rateLimit.active ? (
            <>
              <b>Too many messages at once.</b> You can send again in <span className="tabular-nums">{rateLimit.secondsLeft}</span> s.
            </>
          ) : (
            <>
              <b>Ready.</b> You can send again.
            </>
          )}
        </Banner>
      )}

      <div role="group" aria-label="Start from" className="flex flex-wrap gap-1.5 [@media(max-height:560px)]:hidden">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion.label}
            type="button"
            onClick={() => {
              onChange(suggestion.prefix);
              textarea.current?.focus();
            }}
            className="touch-target rounded-full border border-bp-border bg-bp-surface-2 px-2.5 py-1.5 text-xs text-bp-text-muted hover:border-bp-text-muted/50 hover:text-bp-text"
          >
            {suggestion.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
        <label htmlFor={inputId} className="sr-only">
          Message
        </label>
        <textarea
          ref={textarea}
          id={inputId}
          rows={1}
          value={value}
          maxLength={MAX_QUERY_LENGTH}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          className="max-h-[140px] min-h-[46px] w-full resize-none rounded-[var(--bp-radius)] border border-bp-border bg-bp-surface-1 px-3.5 py-3 text-[15px] leading-[1.45] text-bp-text placeholder:text-bp-text-muted/80"
        />
        <Button type="submit" size="lg" disabled={!canSend} className="h-[46px]">
          <SendHorizontal /> Send
        </Button>
      </div>

      {meter}
    </form>
  );
}
