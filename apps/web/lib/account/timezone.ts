export function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

/** Every zone the browser knows, plus any extras (the saved and detected zone) that its list may spell differently. */
export function timeZoneOptions(extras: readonly (string | null)[]): string[] {
  const zones = new Set<string>(Intl.supportedValuesOf("timeZone"));
  for (const extra of extras) if (extra) zones.add(extra);
  return [...zones].sort();
}
