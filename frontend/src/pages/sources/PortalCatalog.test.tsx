import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AccountPlan, Portal } from "../../types";
import { renderWithClient } from "../../test/renderWithClient";
import { PortalCatalog } from "./PortalCatalog";

const metaState = vi.hoisted(() => ({ value: null as unknown }));
const portalsState = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
const createMutate = vi.hoisted(() => vi.fn());
const createPending = vi.hoisted(() => ({ value: false }));

vi.mock("../../hooks/queries", () => ({
  useMeta: () => ({ data: metaState.value }),
  usePortals: (category?: string, query?: string) => {
    portalsState.value.lastArgs = { category, query };
    return portalsState.value;
  },
}));

vi.mock("../../hooks/mutations", () => ({
  useCreateSource: () => ({ mutateAsync: createMutate, isPending: createPending.value }),
}));

function makePortal(overrides: Partial<Portal> = {}): Portal {
  return {
    id: "stripe",
    company_name: "Stripe",
    category: "unicorn",
    adapter_key: "greenhouse",
    base_url: "https://boards.greenhouse.io/stripe",
    default_config: {},
    supports_auto_apply: false,
    allowed_on_plan: true,
    already_added: false,
    ...overrides,
  };
}

function planAt(usage: number, max: number): AccountPlan {
  return {
    plan: "free",
    effective_plan: "free",
    unlimited: false,
    show_ads: true,
    limits: { max_searches: 5, max_sources: max, max_targets: 5, max_auto_applies_per_day: 5 },
    usage: { searches: 0, sources: usage, targets: 0, auto_applies_last_day: 0 },
    features: {
      digest_mode: false,
      ai_summaries: false,
      site_credentials: false,
      rss_feed: false,
      portal_search: false,
    },
    allowed_scrapers: [],
    allowed_notifiers: [],
  };
}

function renderCatalog(props = {}) {
  return renderWithClient(
    <MemoryRouter>
      <PortalCatalog {...props} />
    </MemoryRouter>,
  );
}

describe("PortalCatalog", () => {
  beforeEach(() => {
    metaState.value = { plan: planAt(0, 10) };
    portalsState.value = {
      data: { items: [makePortal()], categories: ["unicorn"] },
      isPending: false,
      isError: false,
    };
    createMutate.mockReset().mockResolvedValue(undefined);
    createPending.value = false;
  });

  it("shows the loading state", () => {
    portalsState.value = { data: undefined, isPending: true, isError: false };
    renderCatalog();
    expect(screen.getByText("Loading companies...")).toBeInTheDocument();
  });

  it("shows the error banner", () => {
    portalsState.value = { data: undefined, isPending: false, isError: true };
    renderCatalog();
    expect(screen.getByText("Could not load the company catalog.")).toBeInTheDocument();
  });

  it("shows the empty state when there are no matches", () => {
    portalsState.value = {
      data: { items: [], categories: [] },
      isPending: false,
      isError: false,
    };
    renderCatalog();
    expect(screen.getByText("No companies match your filters.")).toBeInTheDocument();
  });

  it("adds a portal and calls onAdded", async () => {
    const onAdded = vi.fn();
    renderCatalog({ onAdded });

    fireEvent.click(screen.getByRole("button", { name: "Add source" }));
    await waitFor(() => expect(createMutate).toHaveBeenCalled());
    expect(onAdded).toHaveBeenCalledWith("Stripe");
  });

  it("reports errors through onError", async () => {
    createMutate.mockRejectedValueOnce(new Error("add failed"));
    const onError = vi.fn();
    renderCatalog({ onError });

    fireEvent.click(screen.getByRole("button", { name: "Add source" }));
    await waitFor(() => expect(onError).toHaveBeenCalledWith("add failed"));
  });

  it("labels an already-added portal", () => {
    portalsState.value = {
      data: { items: [makePortal({ already_added: true })], categories: [] },
      isPending: false,
      isError: false,
    };
    renderCatalog();
    expect(screen.getByRole("button", { name: "Added" })).toBeDisabled();
  });

  it("labels a portal requiring an upgrade", () => {
    portalsState.value = {
      data: { items: [makePortal({ allowed_on_plan: false })], categories: [] },
      isPending: false,
      isError: false,
    };
    renderCatalog();
    expect(screen.getByRole("button", { name: "Pro required" })).toBeDisabled();
  });

  it("labels a portal when the plan is at its source limit", () => {
    metaState.value = { plan: planAt(10, 10) };
    renderCatalog();
    expect(screen.getByRole("button", { name: "At limit" })).toBeDisabled();
  });

  it("treats a missing plan as able to create", () => {
    metaState.value = undefined;
    renderCatalog();
    expect(screen.getByRole("button", { name: "Add source" })).toBeEnabled();
  });

  it("shows the auto-apply chip and adapter code", () => {
    portalsState.value = {
      data: { items: [makePortal({ supports_auto_apply: true })], categories: [] },
      isPending: false,
      isError: false,
    };
    renderCatalog();
    expect(screen.getByText("Auto-apply")).toBeInTheDocument();
    expect(screen.getByText("greenhouse")).toBeInTheDocument();
  });

  it("filters by category tab and search input", () => {
    renderCatalog();

    fireEvent.click(screen.getByRole("tab", { name: "Unicorns" }));
    expect((portalsState.value as { lastArgs?: { category?: string } }).lastArgs?.category).toBe(
      "unicorn",
    );

    fireEvent.click(screen.getByRole("tab", { name: "All" }));
    expect(
      (portalsState.value as { lastArgs?: { category?: string } }).lastArgs?.category,
    ).toBeUndefined();

    fireEvent.change(screen.getByLabelText("Search companies"), {
      target: { value: "strip" },
    });
    expect((portalsState.value as { lastArgs?: { query?: string } }).lastArgs?.query).toBe("strip");
  });

  it("disables the add button while a create is pending", () => {
    createPending.value = true;
    renderCatalog();
    expect(screen.getByRole("button", { name: "Add source" })).toBeDisabled();
  });
});
