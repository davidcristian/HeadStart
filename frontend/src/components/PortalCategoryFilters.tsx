/** Single-select category filter as a labelled button group (not a tablist). */

import { PORTAL_CATEGORY_LABELS } from "../lib/portals";
import type { PortalCategory } from "../types";

type PortalCategoryFiltersProps = {
  category: PortalCategory | "";
  categories: PortalCategory[];
  onChange: (category: PortalCategory | "") => void;
};

export function PortalCategoryFilters({
  category,
  categories,
  onChange,
}: PortalCategoryFiltersProps) {
  return (
    <div className="portal-category-tabs" role="group" aria-label="Portal categories">
      <button
        type="button"
        className={category === "" ? "portal-tab active" : "portal-tab"}
        aria-pressed={category === ""}
        onClick={() => onChange("")}
      >
        All
      </button>
      {categories.map((key) => (
        <button
          key={key}
          type="button"
          className={category === key ? "portal-tab active" : "portal-tab"}
          aria-pressed={category === key}
          onClick={() => onChange(key)}
        >
          {PORTAL_CATEGORY_LABELS[key]}
        </button>
      ))}
    </div>
  );
}
