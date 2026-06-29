/** Structured editor for search post-scrape filters. */

import { Field } from "./ui";
import type { SearchFilterForm } from "../lib/searchFilters";

export function SearchFiltersForm({
  value,
  onChange,
}: {
  value: SearchFilterForm;
  onChange: (next: SearchFilterForm) => void;
}) {
  function update<K extends keyof SearchFilterForm>(key: K, next: SearchFilterForm[K]) {
    onChange({ ...value, [key]: next });
  }

  return (
    <div className="form-grid">
      <Field label="Keywords include" hint="All terms must appear in title, company, or location.">
        <input
          value={value.keywords}
          onChange={(e) => update("keywords", e.target.value)}
          placeholder="engineer backend"
        />
      </Field>
      <Field label="Keywords exclude" hint="Skip jobs containing any of these terms.">
        <input
          value={value.keywordsExclude}
          onChange={(e) => update("keywordsExclude", e.target.value)}
          placeholder="manager intern"
        />
      </Field>
      <Field label="Location contains">
        <input
          value={value.location}
          onChange={(e) => update("location", e.target.value)}
          placeholder="amsterdam, remote"
        />
      </Field>
      <Field label="Workplace">
        <select
          value={value.workplace}
          onChange={(e) => update("workplace", e.target.value as SearchFilterForm["workplace"])}
        >
          <option value="">Any</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
          <option value="onsite">On-site</option>
        </select>
      </Field>
      <Field label="Minimum salary (annual)" hint="Jobs without salary data still pass.">
        <input
          type="number"
          min={0}
          value={value.minSalary}
          onChange={(e) => update("minSalary", e.target.value)}
          placeholder="120000"
        />
      </Field>
      <Field label="Salary currency">
        <select
          value={value.salaryCurrency}
          onChange={(e) => update("salaryCurrency", e.target.value)}
        >
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="GBP">GBP</option>
        </select>
      </Field>
    </div>
  );
}
