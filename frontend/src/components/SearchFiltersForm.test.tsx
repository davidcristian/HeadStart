import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchFiltersForm } from "./SearchFiltersForm";
import { EMPTY_SEARCH_FILTERS, type SearchFilterForm } from "../lib/searchFilters";

function renderForm(overrides: Partial<SearchFilterForm> = {}) {
  const onChange = vi.fn();
  const value: SearchFilterForm = { ...EMPTY_SEARCH_FILTERS, ...overrides };
  render(<SearchFiltersForm value={value} onChange={onChange} />);
  return { onChange, value };
}

describe("SearchFiltersForm", () => {
  it("updates the include keywords", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByPlaceholderText("engineer backend"), {
      target: { value: "backend" },
    });
    expect(onChange).toHaveBeenCalledWith({ ...value, keywords: "backend" });
  });

  it("updates the exclude keywords", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByPlaceholderText("manager intern"), {
      target: { value: "intern" },
    });
    expect(onChange).toHaveBeenCalledWith({ ...value, keywordsExclude: "intern" });
  });

  it("updates the location", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByPlaceholderText("amsterdam, remote"), {
      target: { value: "berlin" },
    });
    expect(onChange).toHaveBeenCalledWith({ ...value, location: "berlin" });
  });

  it("updates the workplace", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByDisplayValue("Any"), { target: { value: "remote" } });
    expect(onChange).toHaveBeenCalledWith({ ...value, workplace: "remote" });
  });

  it("updates the minimum salary", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByPlaceholderText("120000"), { target: { value: "150000" } });
    expect(onChange).toHaveBeenCalledWith({ ...value, minSalary: "150000" });
  });

  it("updates the salary currency", () => {
    const { onChange, value } = renderForm();
    fireEvent.change(screen.getByDisplayValue("USD"), { target: { value: "EUR" } });
    expect(onChange).toHaveBeenCalledWith({ ...value, salaryCurrency: "EUR" });
  });
});
