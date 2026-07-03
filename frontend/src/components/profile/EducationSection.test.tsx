import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EducationEntry } from "../../types";
import { EducationSection, EMPTY_EDUCATION } from "./EducationSection";

function makeRow(overrides: Partial<EducationEntry> = {}): EducationEntry {
  return { ...EMPTY_EDUCATION, ...overrides };
}

describe("EducationSection", () => {
  it("shows the empty-state hint when there are no rows", () => {
    render(<EducationSection education={[]} onEducationChange={vi.fn()} />);

    expect(screen.getByText("No education saved yet.")).toBeInTheDocument();
    expect(screen.queryByText("School 1")).not.toBeInTheDocument();
  });

  it("appends an empty school when Add school is clicked", () => {
    const onChange = vi.fn();
    const existing = [makeRow({ school: "MIT" })];
    render(<EducationSection education={existing} onEducationChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Add school" }));

    expect(onChange).toHaveBeenCalledWith([...existing, { ...EMPTY_EDUCATION }]);
  });

  it("removes the row at the clicked index", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ school: "First" }), makeRow({ school: "Second" })];
    render(<EducationSection education={rows} onEducationChange={onChange} />);

    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);

    expect(onChange).toHaveBeenCalledWith([rows[0]]);
  });

  it("edits every field of a row", () => {
    const onChange = vi.fn();
    const rows = [makeRow()];
    render(<EducationSection education={rows} onEducationChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("University of Example"), {
      target: { value: "Stanford" },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ school: "Stanford" })]);

    fireEvent.change(screen.getByPlaceholderText("Bachelor of Science"), {
      target: { value: "MSc" },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ degree: "MSc" })]);

    fireEvent.change(screen.getByPlaceholderText("Computer Science"), {
      target: { value: "Physics" },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ field_of_study: "Physics" })]);

    fireEvent.change(screen.getByLabelText("Start year"), { target: { value: "2015" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ start_year: 2015 })]);

    fireEvent.change(screen.getByLabelText("End year"), { target: { value: "2019" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ end_year: 2019 })]);

    fireEvent.change(screen.getByPlaceholderText("3.8"), { target: { value: "3.9" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ gpa: "3.9" })]);
  });

  it("clears a year field back to null when emptied", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ start_year: 2015 })];
    render(<EducationSection education={rows} onEducationChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Start year"), { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ start_year: null })]);
  });

  it("labels each school by its 1-based index", () => {
    render(<EducationSection education={[makeRow(), makeRow()]} onEducationChange={vi.fn()} />);

    expect(screen.getByText("School 1")).toBeInTheDocument();
    expect(screen.getByText("School 2")).toBeInTheDocument();
  });
});
