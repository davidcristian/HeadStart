import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { must } from "../../test/must";
import type { WorkExperienceEntry } from "../../types";
import { EMPTY_WORK_EXPERIENCE, WorkExperienceSection } from "./WorkExperienceSection";

function makeRow(overrides: Partial<WorkExperienceEntry> = {}): WorkExperienceEntry {
  return { ...EMPTY_WORK_EXPERIENCE, ...overrides };
}

describe("WorkExperienceSection", () => {
  it("shows the empty-state hint when there are no rows", () => {
    render(<WorkExperienceSection workExperience={[]} onWorkExperienceChange={vi.fn()} />);

    expect(screen.getByText("No work experience saved yet.")).toBeInTheDocument();
    expect(screen.queryByText("Role 1")).not.toBeInTheDocument();
  });

  it("appends an empty role when Add role is clicked", () => {
    const onChange = vi.fn();
    const existing = [makeRow({ job_title: "Engineer" })];
    render(<WorkExperienceSection workExperience={existing} onWorkExperienceChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Add role" }));

    expect(onChange).toHaveBeenCalledWith([...existing, { ...EMPTY_WORK_EXPERIENCE }]);
  });

  it("removes the row at the clicked index", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ job_title: "First" }), makeRow({ job_title: "Second" })];
    render(<WorkExperienceSection workExperience={rows} onWorkExperienceChange={onChange} />);

    fireEvent.click(must(screen.getAllByRole("button", { name: "Remove" })[0]));

    expect(onChange).toHaveBeenCalledWith([rows[1]]);
  });

  it("edits the text and number fields of a row", () => {
    const onChange = vi.fn();
    const rows = [makeRow()];
    render(<WorkExperienceSection workExperience={rows} onWorkExperienceChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Software Engineer"), {
      target: { value: "Staff Engineer" },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ job_title: "Staff Engineer" })]);

    fireEvent.change(screen.getByPlaceholderText("ACME Corp"), { target: { value: "Globex" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ company: "Globex" })]);

    fireEvent.change(screen.getByPlaceholderText("San Francisco, CA"), {
      target: { value: "Berlin" },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ location: "Berlin" })]);

    fireEvent.change(screen.getByLabelText("Start month"), { target: { value: "3" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ start_month: 3 })]);

    fireEvent.change(screen.getByLabelText("Start year"), { target: { value: "2020" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ start_year: 2020 })]);

    fireEvent.change(screen.getByPlaceholderText("Responsibilities and achievements"), {
      target: { value: "Built things." },
    });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ description: "Built things." })]);
  });

  it("shows end-date fields for a non-current role and edits them", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ end_month: 6, end_year: 2019 })];
    render(<WorkExperienceSection workExperience={rows} onWorkExperienceChange={onChange} />);

    fireEvent.change(screen.getByLabelText("End month"), { target: { value: "9" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ end_month: 9, end_year: 2019 })]);

    fireEvent.change(screen.getByLabelText("End year"), { target: { value: "2021" } });
    expect(onChange).toHaveBeenLastCalledWith([makeRow({ end_month: 6, end_year: 2021 })]);
  });

  it("hides end-date fields and clears them when marked as current", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ end_month: 6, end_year: 2019 })];
    const { rerender } = render(
      <WorkExperienceSection workExperience={rows} onWorkExperienceChange={onChange} />,
    );

    fireEvent.click(screen.getByLabelText("I currently work here"));
    expect(onChange).toHaveBeenLastCalledWith([
      makeRow({ is_current: true, end_month: null, end_year: null }),
    ]);

    rerender(
      <WorkExperienceSection
        workExperience={[makeRow({ is_current: true })]}
        onWorkExperienceChange={onChange}
      />,
    );
    expect(screen.queryByLabelText("End month")).not.toBeInTheDocument();
  });

  it("keeps existing end dates when unchecking the current flag", () => {
    const onChange = vi.fn();
    const rows = [makeRow({ is_current: true, end_month: 4, end_year: 2018 })];
    render(<WorkExperienceSection workExperience={rows} onWorkExperienceChange={onChange} />);

    fireEvent.click(screen.getByLabelText("I currently work here"));
    expect(onChange).toHaveBeenLastCalledWith([
      makeRow({ is_current: false, end_month: 4, end_year: 2018 }),
    ]);
  });

  it("does not nest the current-role checkbox label inside a Field label (FRO-26)", () => {
    render(<WorkExperienceSection workExperience={[makeRow()]} onWorkExperienceChange={vi.fn()} />);

    const checkbox = screen.getByRole("checkbox", { name: "I currently work here" });
    const checkboxLabel = checkbox.closest("label");
    expect(checkboxLabel).not.toBeNull();
    expect(checkboxLabel?.parentElement?.closest("label")).toBeNull();
    expect(screen.getByText("Current role").tagName).toBe("SPAN");
  });

  it("labels each role by its 1-based index", () => {
    const rows = [makeRow(), makeRow()];
    render(<WorkExperienceSection workExperience={rows} onWorkExperienceChange={vi.fn()} />);

    const cards = screen.getAllByText(/^Role \d$/);
    expect(
      within(must(cards[0]).parentElement as HTMLElement).getByText("Role 1"),
    ).toBeInTheDocument();
    expect(screen.getByText("Role 2")).toBeInTheDocument();
  });
});
