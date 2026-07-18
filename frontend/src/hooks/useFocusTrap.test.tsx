import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { useFocusTrap } from "./useFocusTrap";

function Dialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(true, ref, onClose);
  return (
    <div ref={ref} role="dialog">
      <button>first</button>
      <button>last</button>
    </div>
  );
}

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>open</button>
      {open && <Dialog onClose={() => setOpen(false)} />}
    </>
  );
}

function InactiveDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(false, ref, onClose);
  return (
    <div ref={ref} role="dialog">
      <button>first</button>
      <button>last</button>
    </div>
  );
}

function NullRefDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  // Intentionally never attach the ref, so containerRef.current stays null.
  useFocusTrap(true, ref, onClose);
  return (
    <div role="dialog">
      <button>outside</button>
    </div>
  );
}

function EmptyDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(true, ref, onClose);
  return <div ref={ref} role="dialog" />;
}

function ThreeButtonDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(true, ref, onClose);
  return (
    <div ref={ref} role="dialog">
      <button>first</button>
      <button>middle</button>
      <button>last</button>
    </div>
  );
}

function FocusContainerDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(true, ref, onClose, { focusContainer: true });
  return (
    <div ref={ref} role="dialog" tabIndex={-1}>
      <button>Close</button>
      <button>Submit</button>
    </div>
  );
}

describe("useFocusTrap", () => {
  it("moves focus to the first focusable element when activated", () => {
    render(<Dialog onClose={() => {}} />);
    expect(screen.getByText("first")).toHaveFocus();
  });

  it("moves focus to the container when focusContainer is set", () => {
    render(<FocusContainerDialog onClose={() => {}} />);
    expect(screen.getByRole("dialog")).toHaveFocus();
    expect(screen.getByText("Close")).not.toHaveFocus();
  });

  it("Tabs from a focused container into the first focusable child", () => {
    render(<FocusContainerDialog onClose={() => {}} />);
    expect(screen.getByRole("dialog")).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByText("Close")).toHaveFocus();
  });

  it("Shift+Tabs from a focused container to the last focusable child", () => {
    render(<FocusContainerDialog onClose={() => {}} />);
    expect(screen.getByRole("dialog")).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByText("Submit")).toHaveFocus();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(<Dialog onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("wraps focus from the last element back to the first on Tab", () => {
    render(<Dialog onClose={() => {}} />);
    const last = screen.getByText("last");
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByText("first")).toHaveFocus();
  });

  it("wraps focus from the first element to the last on Shift+Tab", () => {
    render(<Dialog onClose={() => {}} />);
    const first = screen.getByText("first");
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByText("last")).toHaveFocus();
  });

  it("restores focus to the trigger when the dialog unmounts", () => {
    render(<Harness />);
    const trigger = screen.getByText("open");
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByText("first")).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(trigger).toHaveFocus();
  });

  it("does nothing when inactive", () => {
    const outside = document.createElement("button");
    outside.textContent = "outside";
    document.body.appendChild(outside);
    outside.focus();

    const onClose = vi.fn();
    render(<InactiveDialog onClose={onClose} />);

    // No focus moved into the dialog, and Escape is ignored.
    expect(outside).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();

    document.body.removeChild(outside);
  });

  it("does nothing when the container ref is not attached", () => {
    const onClose = vi.fn();
    render(<NullRefDialog onClose={onClose} />);

    // The keydown listener is never registered, so Escape is ignored.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("ignores keys other than Tab and Escape", () => {
    const onClose = vi.fn();
    render(<Dialog onClose={onClose} />);
    const first = screen.getByText("first");

    fireEvent.keyDown(document, { key: "a" });
    expect(onClose).not.toHaveBeenCalled();
    expect(first).toHaveFocus();
  });

  it("does nothing on Tab when there are no focusable elements", () => {
    const onClose = vi.fn();
    render(<EmptyDialog onClose={onClose} />);
    expect(() => fireEvent.keyDown(document, { key: "Tab" })).not.toThrow();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("wraps to the last element on Shift+Tab when focus is outside the container", () => {
    render(<Dialog onClose={() => {}} />);
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByText("last")).toHaveFocus();

    document.body.removeChild(outside);
  });

  it("wraps to the first element on Tab when focus is outside the container", () => {
    render(<Dialog onClose={() => {}} />);
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();

    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByText("first")).toHaveFocus();

    document.body.removeChild(outside);
  });

  it("does not intercept Tab in the middle of the focusable list", () => {
    render(<ThreeButtonDialog onClose={() => {}} />);
    const middle = screen.getByText("middle");
    middle.focus();

    // Tab from the middle element: neither first nor last, still inside the
    // container -> the hook lets the browser handle it and focus stays put.
    fireEvent.keyDown(document, { key: "Tab" });
    expect(middle).toHaveFocus();
  });

  it("does not intercept Shift+Tab in the middle of the focusable list", () => {
    render(<ThreeButtonDialog onClose={() => {}} />);
    const middle = screen.getByText("middle");
    middle.focus();

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(middle).toHaveFocus();
  });
});
