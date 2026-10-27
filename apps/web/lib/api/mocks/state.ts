import type { Usage } from "../types";
import { meFor } from "./data";

function counter(base: Usage) {
  let used = base.used;
  return {
    current(): Usage {
      return { ...base, used };
    },
    isExhausted(): boolean {
      return used >= base.limit;
    },
    spend(): Usage {
      used = Math.min(used + 1, base.limit);
      return this.current();
    },
    leaveOneChat(): void {
      used = base.limit - 1;
    },
    reset(): void {
      used = base.used;
    },
  };
}

/** The free plan's chat counter, shared by `/me` and the predict stream so the two always agree. */
export const mockUsage = counter(meFor("free").usage);

/** A demo user's 10 chats in total; a fresh demo account has used none. */
export const mockDemoUsage = counter({ ...meFor("demo").usage, used: 0 });

export function resetMockUsage(): void {
  mockUsage.reset();
  mockDemoUsage.reset();
}
