const MONEY = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", currencyDisplay: "narrowSymbol" });

export function formatMoney(cents: number): string {
  return MONEY.format(cents / 100);
}

export function formatPercent(fraction: number): string {
  return `${Number.parseFloat((fraction * 100).toFixed(1))}%`;
}

export function formatAgo(iso: string, now: number = Date.now()): string {
  const minutes = Math.floor((now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} h ago`;
  return `${Math.floor(minutes / 1440)} d ago`;
}

export type CostStatus = "healthy" | "watch" | "high";

export function costStatus(ratio: number | null): CostStatus | null {
  if (ratio === null) return null;
  if (ratio >= 0.5) return "high";
  return ratio >= 0.3 ? "watch" : "healthy";
}

/** A y-axis whose top is a multiple of `step` times four, so the gridlines are whole numbers. */
export function axisScale(max: number, step: number): { top: number; ticks: number[] } {
  const top = Math.max(step, Math.ceil(max / step) * step);
  return { top, ticks: [0, 1, 2, 3, 4].map((index) => (top / 4) * index) };
}

export function labelEvery(days: number): number {
  if (days <= 7) return 1;
  return days <= 30 ? 7 : 14;
}
