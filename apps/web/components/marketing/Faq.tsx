"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useState, type KeyboardEvent } from "react";

import { AgentOrb } from "@/components/signature/AgentOrb";

import { FAQ_ENTRIES, nextFaqIndex } from "./faq-content";
import "./marketing.css";

const SEND_SPRING = { type: "spring", bounce: 0.28, duration: 0.42 } as const;
const SHIFT_SPRING = { type: "spring", bounce: 0.1, duration: 0.4 } as const;
const LEAVE = { duration: 0.16, ease: "easeIn" } as const;

/**
 * The FAQ as a conversation: each question is a grey bubble on the left, and the answer pops in
 * as a red bubble from the orb on the right. One answer is open at a time.
 */
export function Faq() {
  const [openId, setOpenId] = useState<string | null>(FAQ_ENTRIES[0].id);

  const moveFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (!target.matches("[data-faq-question]")) return;
    const questions = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[data-faq-question]")];
    const next = nextFaqIndex(event.key, questions.indexOf(target as HTMLButtonElement), questions.length);
    if (next === null) return;
    event.preventDefault();
    questions[next].focus();
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative mx-auto flex w-full max-w-[576px] flex-col gap-3" onKeyDown={moveFocus}>
        <AnimatePresence mode="popLayout" initial={false}>
          {FAQ_ENTRIES.flatMap((entry) => {
            const open = entry.id === openId;
            const nodes = [
              <motion.button
                key={`q-${entry.id}`}
                layout
                transition={{ layout: SHIFT_SPRING }}
                type="button"
                id={`faq-q-${entry.id}`}
                data-faq-question
                aria-expanded={open}
                aria-controls={open ? `faq-a-${entry.id}` : undefined}
                whileTap={{ scale: 0.97 }}
                onClick={() => setOpenId(open ? null : entry.id)}
                className="faq-bubble-question max-w-[85%] cursor-pointer self-start rounded-[18px_18px_18px_6px] border-0 px-4 py-2.5 text-left text-[15px] leading-[1.4] tracking-[-0.01em] text-white"
              >
                {entry.question}
              </motion.button>,
            ];
            if (open) {
              nodes.push(
                <motion.div
                  key={`a-${entry.id}`}
                  layout
                  initial={{ opacity: 0, y: 12, scale: 0.6 }}
                  animate={{ opacity: 1, y: 0, scale: 1, transition: SEND_SPRING }}
                  exit={{ opacity: 0, scale: 0.9, transition: LEAVE }}
                  style={{ transformOrigin: "100% 100%" }}
                  className="flex items-end justify-end gap-2"
                >
                  <div
                    id={`faq-a-${entry.id}`}
                    role="region"
                    aria-labelledby={`faq-q-${entry.id}`}
                    className="max-w-[85%] rounded-[18px_18px_6px_18px] bg-bp-red px-4 py-2.5 text-[15px] leading-[1.45] tracking-[-0.01em] text-white"
                  >
                    {entry.answer}
                  </div>
                  <span className="grid size-8 flex-none place-items-center overflow-hidden rounded-full bg-white/[0.07]">
                    <AgentOrb state={{ phase: "idle" }} size={28} />
                  </span>
                </motion.div>,
              );
            }
            return nodes;
          })}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
