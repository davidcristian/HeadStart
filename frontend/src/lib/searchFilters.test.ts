import { describe, expect, it } from "vitest";
import { EMPTY_SEARCH_FILTERS, filtersToForm, formToFilters } from "./searchFilters";

describe("searchFilters", () => {
  it("round-trips structured filters", () => {
    const form = {
      ...EMPTY_SEARCH_FILTERS,
      keywords: "engineer",
      keywordsExclude: "manager",
      location: "remote",
      workplace: "remote" as const,
      minSalary: "150000",
      salaryCurrency: "USD",
    };

    expect(formToFilters(form)).toEqual({
      keywords: "engineer",
      keywords_exclude: "manager",
      location: "remote",
      workplace: "remote",
      min_salary: 150000,
      salary_currency: "USD",
    });
    expect(filtersToForm(formToFilters(form))).toEqual(form);
  });

  it("omits empty fields", () => {
    expect(formToFilters(EMPTY_SEARCH_FILTERS)).toEqual({});
  });
});
