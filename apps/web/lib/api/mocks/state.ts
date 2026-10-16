import type { Usage } from "../types";
import { meFor } from "./data";

const freeUsage = meFor("free").usage;

let used = freeUsage.used;

/** The free plan's chat counter, shared by `/me` and the predict stream so the two always agree. */
export const mockUsage = {
  current(): Usage {
    return { ...freeUsage, used };
  },
  isExhausted(): boolean {
    return used >= freeUsage.limit;
  },
  spend(): Usage {
    used = Math.min(used + 1, freeUsage.limit);
    return this.current();
  },
  leaveOneChat(): void {
    used = freeUsage.limit - 1;
  },
  reset(): void {
    used = freeUsage.used;
  },
};
