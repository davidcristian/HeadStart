/** Helpers for search filter JSON used by the API. */

import type { Json } from "../types";

export type WorkplaceFilter = "" | "remote" | "hybrid" | "onsite";

export interface SearchFilterForm {
  keywords: string;
  keywordsExclude: string;
  location: string;
  workplace: WorkplaceFilter;
  minSalary: string;
  salaryCurrency: string;
}

export const EMPTY_SEARCH_FILTERS: SearchFilterForm = {
  keywords: "",
  keywordsExclude: "",
  location: "",
  workplace: "",
  minSalary: "",
  salaryCurrency: "USD",
};

export function filtersToForm(filters: Json): SearchFilterForm {
  const workplace = String(filters.workplace ?? "");
  return {
    keywords: stringField(filters.keywords ?? filters.keywords_include),
    keywordsExclude: stringField(filters.keywords_exclude),
    location: stringField(filters.location),
    workplace:
      workplace === "remote" || workplace === "hybrid" || workplace === "onsite" ? workplace : "",
    minSalary: filters.min_salary != null ? String(filters.min_salary) : "",
    salaryCurrency: stringField(filters.salary_currency) || "USD",
  };
}

export function formToFilters(form: SearchFilterForm): Json {
  const filters: Json = {};
  const keywords = form.keywords.trim();
  const keywordsExclude = form.keywordsExclude.trim();
  const location = form.location.trim();
  const minSalary = Number(form.minSalary);

  if (keywords) filters.keywords = keywords;
  if (keywordsExclude) filters.keywords_exclude = keywordsExclude;
  if (location) filters.location = location;
  if (form.workplace) filters.workplace = form.workplace;
  if (form.minSalary.trim() && Number.isFinite(minSalary) && minSalary > 0) {
    filters.min_salary = Math.round(minSalary);
    filters.salary_currency = form.salaryCurrency || "USD";
  }
  return filters;
}

function stringField(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value == null) return "";
  return String(value);
}
