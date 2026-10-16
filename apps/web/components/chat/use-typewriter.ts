"use client";

import { useEffect, useRef, useState } from "react";

const CHARS_PER_TICK = 3;

type TypewriterOptions = {
  enabled: boolean;
  charsPerSecond: number;
  onDone?: () => void;
};

/** Reveals `text` three characters per tick at the given speed; disabled means all of it at once. */
export function useTypewriter(text: string, { enabled, charsPerSecond, onDone }: TypewriterOptions) {
  const [count, setCount] = useState(0);
  const onDoneRef = useRef(onDone);
  const doneForRef = useRef<string | null>(null);

  useEffect(() => {
    onDoneRef.current = onDone;
  });

  const instant = !enabled || text === "";
  const shown = instant ? text.length : Math.min(count, text.length);
  const finished = shown >= text.length;

  useEffect(() => {
    if (instant) return;
    const timer = setInterval(() => setCount((current) => current + CHARS_PER_TICK), (CHARS_PER_TICK * 1000) / charsPerSecond);
    return () => clearInterval(timer);
  }, [instant, charsPerSecond, text]);

  useEffect(() => {
    if (!finished || text === "" || doneForRef.current === text) return;
    doneForRef.current = text;
    onDoneRef.current?.();
  }, [finished, text]);

  return { visible: text.slice(0, shown), typing: !finished };
}
