import { describe, expect, it } from "vitest";
import { EMPTY_SEARCH_FILTERS, filtersToForm, formToFilters } from "./searchFilters";

describe("searchFilters branches", () => {
  describe("filtersToForm", () => {
    it("joins array fields and coerces numbers via stringField", () => {
      const form = filtersToForm({
        keywords: ["engineer", "python"],
        keywords_exclude: ["manager"],
        location: 42,
        min_salary: 120000,
      });
      expect(form.keywords).toBe("engineer, python");
      expect(form.keywordsExclude).toBe("manager");
      expect(form.location).toBe("42");
      expect(form.minSalary).toBe("120000");
    });

    it("falls back to keywords_include when keywords is absent", () => {
      expect(filtersToForm({ keywords_include: "backend" }).keywords).toBe("backend");
    });

    it("drops an unknown workplace value to empty", () => {
      expect(filtersToForm({ workplace: "anywhere" }).workplace).toBe("");
    });

    it("keeps a hybrid workplace value", () => {
      expect(filtersToForm({ workplace: "hybrid" }).workplace).toBe("hybrid");
    });

    it("keeps an onsite workplace value", () => {
      expect(filtersToForm({ workplace: "onsite" }).workplace).toBe("onsite");
    });

    it("returns empty min salary when the value is null", () => {
      expect(filtersToForm({ min_salary: null }).minSalary).toBe("");
    });

    it("defaults salary currency to USD when missing", () => {
      expect(filtersToForm({}).salaryCurrency).toBe("USD");
    });

    it("keeps a provided salary currency", () => {
      expect(filtersToForm({ salary_currency: "EUR" }).salaryCurrency).toBe("EUR");
    });

    it("returns empty string for null string fields", () => {
      expect(filtersToForm({ keywords: null }).keywords).toBe("");
    });

    it("coerces non-string, non-array, non-null values to string", () => {
      expect(filtersToForm({ keywords: true }).keywords).toBe("true");
    });
  });

  describe("formToFilters", () => {
    it("ignores a non-numeric min salary", () => {
      const filters = formToFilters({ ...EMPTY_SEARCH_FILTERS, minSalary: "abc" });
      expect(filters.min_salary).toBeUndefined();
      expect(filters.salary_currency).toBeUndefined();
    });

    it("ignores a zero or negative min salary", () => {
      expect(formToFilters({ ...EMPTY_SEARCH_FILTERS, minSalary: "0" }).min_salary).toBeUndefined();
    });

    it("falls back to USD when salary currency is blank but salary is set", () => {
      const filters = formToFilters({
        ...EMPTY_SEARCH_FILTERS,
        minSalary: "100000",
        salaryCurrency: "",
      });
      expect(filters.min_salary).toBe(100000);
      expect(filters.salary_currency).toBe("USD");
    });

    it("rounds fractional salaries", () => {
      expect(formToFilters({ ...EMPTY_SEARCH_FILTERS, minSalary: "100000.7" }).min_salary).toBe(
        100001,
      );
    });
  });
});
