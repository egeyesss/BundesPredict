/** A hard navigation, wrapped so tests can observe it (jsdom cannot navigate). */
export function navigate(url: string): void {
  window.location.assign(url);
}
