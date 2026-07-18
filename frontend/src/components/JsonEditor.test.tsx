import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { JsonEditor } from "./JsonEditor";
import type { Json } from "../types";

describe("JsonEditor", () => {
  it("renders the serialized value with the default rows", () => {
    const onChange = vi.fn();
    render(<JsonEditor value={{ a: 1 }} onChange={onChange} />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe(JSON.stringify({ a: 1 }, null, 2));
    expect(textarea).toHaveAttribute("rows", "4");
    expect(textarea).not.toHaveClass("invalid");
  });

  it("respects a custom rows prop", () => {
    render(<JsonEditor value={{}} onChange={vi.fn()} rows={10} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "10");
  });

  it("reports valid JSON back to the parent", () => {
    const onChange = vi.fn();
    render(<JsonEditor value={{}} onChange={onChange} />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: '{"b":2}' } });

    expect(onChange).toHaveBeenLastCalledWith({ b: 2 }, true);
    expect(screen.queryByText(/Invalid JSON/)).not.toBeInTheDocument();
  });

  it("treats an empty textarea as an empty object", () => {
    const onChange = vi.fn();
    render(<JsonEditor value={{ a: 1 }} onChange={onChange} />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "   " } });

    expect(onChange).toHaveBeenLastCalledWith({}, true);
    expect(screen.queryByText(/Invalid JSON/)).not.toBeInTheDocument();
  });

  it("surfaces a parse error and keeps the last valid value", () => {
    const onChange = vi.fn();
    const value: Json = { a: 1 };
    render(<JsonEditor value={value} onChange={onChange} />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "{ not json" } });

    expect(onChange).toHaveBeenLastCalledWith(value, false);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/Invalid JSON:/);
    expect(alert).toHaveAttribute("aria-live", "assertive");
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveClass("invalid");
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveAttribute("aria-describedby", alert.id);
  });

  it("clears invalid ARIA state once JSON becomes valid again", () => {
    render(<JsonEditor value={{}} onChange={vi.fn()} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "broken" } });
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: '{"ok":true}' } });
    expect(textarea).not.toHaveAttribute("aria-invalid");
    expect(textarea).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("re-syncs the text when the parent value changes", () => {
    function Harness() {
      const [value, setValue] = useState<Json>({ a: 1 });
      return (
        <div>
          <button onClick={() => setValue({ c: 3 })}>reset</button>
          <JsonEditor value={value} onChange={() => undefined} />
        </div>
      );
    }
    render(<Harness />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    // Introduce a parse error first so the re-sync clears it.
    fireEvent.change(textarea, { target: { value: "broken" } });
    expect(screen.getByText(/Invalid JSON:/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "reset" }));

    expect(textarea.value).toBe(JSON.stringify({ c: 3 }, null, 2));
    expect(screen.queryByText(/Invalid JSON/)).not.toBeInTheDocument();
  });
});
