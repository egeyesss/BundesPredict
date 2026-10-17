"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLayoutEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

import "./otp-input.css";

export type OtpStatus = "idle" | "verifying" | "error" | "success";

type OtpInputProps = {
  /** Accessible name for the whole group. */
  label: string;
  length: number;
  value: string;
  onChange: (value: string) => void;
  /** Called once each time the last slot gets filled. */
  onComplete?: (value: string) => void;
  status?: OtpStatus;
  /** Draws a dash after this many slots, for codes shown as `ABCD-EFGH`. */
  separatorAfter?: number;
  autoFocus?: boolean;
  /** Read-only without changing the look, e.g. while a new code is being requested. */
  disabled?: boolean;
  className?: string;
};

const ALLOWED = /[A-Z0-9]/;
const ROLL = { type: "spring", stiffness: 500, damping: 34 } as const;
const CARET = { type: "spring", stiffness: 500, damping: 40 } as const;
const INSTANT = { duration: 0 } as const;

const normalise = (raw: string) =>
  [...raw.toUpperCase()].filter((character) => ALLOWED.test(character)).join("");

export function OtpInput({
  label,
  length,
  value,
  onChange,
  onComplete,
  status = "idle",
  separatorAfter,
  autoFocus = false,
  disabled = false,
  className,
}: OtpInputProps) {
  const reducedMotion = useReducedMotion() ?? false;
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const cells = useRef<(HTMLDivElement | null)[]>([]);
  const [focused, setFocused] = useState<number | null>(null);
  const [caretX, setCaretX] = useState(0);
  const locked = disabled || status === "verifying" || status === "success";
  // Keystrokes can arrive before the parent re-renders with the new value, so each handler
  // builds on the last value this input committed instead of the possibly stale prop.
  const latest = useRef(value);

  useLayoutEffect(() => {
    latest.current = value;
  }, [value]);

  useLayoutEffect(() => {
    if (autoFocus) inputs.current[0]?.focus();
  }, [autoFocus]);

  useLayoutEffect(() => {
    const cell = focused === null ? null : cells.current[focused];
    if (cell) setCaretX(cell.offsetLeft + cell.offsetWidth / 2 - 1);
  }, [focused]);

  const focusAt = (index: number) => {
    const input = inputs.current[Math.min(Math.max(index, 0), length - 1)];
    input?.focus();
    input?.select();
  };

  const commit = (next: string) => {
    const bounded = next.slice(0, length);
    if (bounded === latest.current) return;
    latest.current = bounded;
    onChange(bounded);
    if (bounded.length === length) onComplete?.(bounded);
  };

  const handleInput = (index: number, raw: string) => {
    if (locked) return;
    const value = latest.current;
    const characters = normalise(raw);
    if (!characters) return;
    const current = value[index] ?? "";
    // Typing into a filled slot leaves old+new in the field; anything longer is a paste or SMS autofill.
    const typed = characters.length === 1 ? characters : characters.length === 2 && characters[0] === current ? characters[1] : null;
    if (typed === null) {
      const next = value.slice(0, index) + characters;
      commit(next);
      focusAt(Math.min(next.length, length - 1));
      return;
    }
    commit(value.slice(0, index) + typed + value.slice(index + 1));
    focusAt(index + 1);
  };

  const handleKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (locked) return;
    const value = latest.current;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAt(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAt(index + 1);
    } else if (event.key === "Backspace") {
      event.preventDefault();
      if (value[index]) {
        commit(value.slice(0, index) + value.slice(index + 1));
      } else if (index > 0) {
        commit(value.slice(0, index - 1) + value.slice(index));
        focusAt(index - 1);
      }
    }
  };

  const handlePaste = (index: number, event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    if (locked) return;
    const value = latest.current;
    const characters = normalise(event.clipboardData.getData("text"));
    if (!characters) return;
    const next = (value.slice(0, index) + characters).slice(0, length);
    commit(next);
    focusAt(Math.min(next.length, length - 1));
  };

  // Clicking past the first gap lands on the gap, so the code stays contiguous.
  const handlePointerDown = (index: number, event: React.PointerEvent<HTMLInputElement>) => {
    const target = Math.min(index, value.length);
    if (target !== index) {
      event.preventDefault();
      focusAt(target);
    }
  };

  const showCaret = focused !== null && !value[focused] && !locked;

  return (
    <div role="group" aria-label={label} data-status={status} className={cn("otp", className)}>
      <motion.div
        className="otp-row"
        animate={status === "error" && !reducedMotion ? { x: [0, -5, 4, -2, 0] } : { x: 0 }}
        transition={{ duration: status === "error" && !reducedMotion ? 0.32 : 0, ease: "easeOut" }}
      >
        {Array.from({ length }, (_, index) => {
          const character = value[index] ?? "";
          return (
            <div key={index} className="contents">
              {separatorAfter !== undefined && index === separatorAfter && <span className="otp-sep" aria-hidden="true" />}
              <div
                className="otp-cell"
                ref={(element) => {
                  cells.current[index] = element;
                }}
              >
                <input
                  ref={(element) => {
                    inputs.current[index] = element;
                  }}
                  className="otp-slot"
                  type="text"
                  inputMode="text"
                  autoCapitalize="characters"
                  autoCorrect="off"
                  spellCheck={false}
                  autoComplete={index === 0 ? "one-time-code" : "off"}
                  aria-label={`Character ${index + 1} of ${length}`}
                  aria-invalid={status === "error" ? true : undefined}
                  readOnly={locked}
                  value={character}
                  onChange={(event) => handleInput(index, event.target.value)}
                  onKeyDown={(event) => handleKeyDown(index, event)}
                  onPaste={(event) => handlePaste(index, event)}
                  onPointerDown={(event) => handlePointerDown(index, event)}
                  onFocus={(event) => {
                    setFocused(index);
                    event.target.select();
                  }}
                  onBlur={(event) => {
                    if (!event.relatedTarget || !inputs.current.includes(event.relatedTarget as HTMLInputElement)) setFocused(null);
                  }}
                />
                <svg className="otp-ring" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                  <motion.rect
                    x="1"
                    y="1"
                    width="98"
                    height="98"
                    rx="27"
                    initial={false}
                    animate={status === "success" ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
                    transition={reducedMotion ? INSTANT : { duration: 0.45, ease: "easeOut", delay: status === "success" ? 0.15 + index * 0.05 : 0 }}
                  />
                </svg>
                <span className="otp-char-box" aria-hidden="true">
                  <AnimatePresence initial={false} custom={character ? "-110%" : "110%"}>
                    {character && (
                      <motion.span
                        key={character}
                        className="otp-char"
                        custom={character ? "-110%" : "110%"}
                        variants={{
                          enter: { y: "110%" },
                          center: { y: "0%" },
                          exit: (direction: string) => ({ y: direction }),
                        }}
                        initial="enter"
                        animate="center"
                        exit="exit"
                        transition={reducedMotion ? INSTANT : ROLL}
                      >
                        {character}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </span>
              </div>
            </div>
          );
        })}
        {showCaret && (
          <motion.span
            className="otp-caret"
            aria-hidden="true"
            initial={{ x: caretX }}
            animate={{ x: caretX }}
            transition={reducedMotion ? INSTANT : CARET}
          />
        )}
      </motion.div>
    </div>
  );
}
