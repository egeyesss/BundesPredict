/** True when the element is laid out and not inside a layer the page has switched off (the island keeps its hidden layers `inert`). */
export function isVisible(element: Element): boolean {
  if (element.getClientRects().length === 0) return false;
  return element.closest("[inert]") === null;
}

/** The first visible element for the first name that has one, so a name used on several cards picks the topmost. */
export function findAnchor(names: readonly string[], root: ParentNode = document): HTMLElement | null {
  for (const name of names) {
    const match = [...root.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`)].find(isVisible);
    if (match) return match;
  }
  return null;
}
