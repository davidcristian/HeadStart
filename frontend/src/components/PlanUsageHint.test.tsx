import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { sampleAccountPlan } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type { AccountPlan } from "../types";
import { PlanUsageHint } from "./PlanUsageHint";

function render(plan: AccountPlan, resource: "searches" | "sources" | "targets") {
  return renderWithClient(
    <MemoryRouter>
      <PlanUsageHint plan={plan} resource={resource} />
    </MemoryRouter>,
  );
}

const freePlan: AccountPlan = {
  ...sampleAccountPlan,
  plan: "free",
  effective_plan: "free",
  unlimited: false,
  limits: { max_searches: 3, max_sources: 3, max_targets: 1, max_auto_applies_per_day: 3 },
  usage: { searches: 1, sources: 3, targets: 0, auto_applies_last_day: 0 },
};

describe("PlanUsageHint", () => {
  it("shows the admin note for unlimited plans", () => {
    render({ ...sampleAccountPlan, unlimited: true }, "searches");

    expect(screen.getByText("Admin accounts have no plan limits.")).toBeInTheDocument();
  });

  it("shows usage below the cap without an upgrade prompt", () => {
    render(freePlan, "searches");

    expect(screen.getByText(/1 \/ 3 searches used/)).toBeInTheDocument();
    expect(screen.getByText(/Free plan/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View plans" })).not.toBeInTheDocument();
  });

  it("shows the at-cap message and upgrade link when the cap is reached", () => {
    render(freePlan, "sources");

    expect(screen.getByText(/3 \/ 3 sources used/)).toBeInTheDocument();
    expect(screen.getByText(/Free plan limit reached for sources/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View plans" })).toHaveAttribute("href", "/pricing");
  });

  it("maps the targets resource to the notification-channels label", () => {
    render({ ...freePlan, usage: { ...freePlan.usage, targets: 1 } }, "targets");

    expect(screen.getByText(/1 \/ 1 notification channels used/)).toBeInTheDocument();
  });
});
