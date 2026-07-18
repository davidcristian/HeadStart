/** Accessibility helper for modal-style overlays (e.g. the mobile "More" sheet).
 *
 * While `active`, it: moves focus into the container, keeps Tab/Shift+Tab cycling
 * within it (focus trap), closes on Escape, and restores focus to the previously
 * focused element when it deactivates. Keyboard and screen-reader users can no
 * longer tab "behind" an open dialog or get stuck in it.
 *
 * Pass `{ focusContainer: true }` when the first focusable child is a dismiss
 * control (e.g. Close) so initial focus lands on the dialog itself (needs
 * `tabIndex={-1}` on the container) rather than announcing only that button.
 */

import { useEffect } from "react";
import type { RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

export type FocusTrapOptions = {
  /** Focus the container (needs tabIndex) instead of the first focusable child. */
  focusContainer?: boolean;
};

export function useFocusTrap(
  active: boolean,
  containerRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  options?: FocusTrapOptions,
): void {
  const focusContainer = options?.focusContainer === true;

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    const focusable = (): HTMLElement[] =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));

    if (focusContainer) {
      container.focus();
    } else {
      focusable()[0]?.focus();
    }

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const items = focusable();
      if (items.length === 0) {
        // Container may hold focus with no tabbable children; keep it there.
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement;
      // tabIndex=-1 containers are focusable but excluded from FOCUSABLE_SELECTOR.
      const onContainer = current === container;

      if (event.shiftKey) {
        if (current === first || onContainer || !container!.contains(current)) {
          event.preventDefault();
          last.focus();
        }
      } else if (current === last || onContainer || !container!.contains(current)) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [active, containerRef, onClose, focusContainer]);
}
