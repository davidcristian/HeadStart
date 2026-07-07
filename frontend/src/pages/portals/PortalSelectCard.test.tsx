import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Portal } from "../../types";
import { renderWithClient } from "../../test/renderWithClient";
import { PortalSelectCard } from "./PortalSelectCard";

function makePortal(overrides: Partial<Portal> = {}): Portal {
  return {
    id: "stripe",
    company_name: "Stripe",
    category: "unicorn",
    adapter_key: "greenhouse",
    base_url: "https://boards.greenhouse.io/stripe",
    default_config: {},
    supports_auto_apply: true,
    allowed_on_plan: true,
    already_added: false,
    ...overrides,
  };
}

describe("PortalSelectCard", () => {
  it("renders an unchecked card and fires onToggle", () => {
    const onToggle = vi.fn();
    renderWithClient(
      <ul>
        <PortalSelectCard portal={makePortal()} checked={false} onToggle={onToggle} />
      </ul>,
    );

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).not.toBeChecked();
    expect(screen.getByText("Stripe")).toBeInTheDocument();
    expect(screen.getByText("Unicorns")).toBeInTheDocument();
    expect(screen.queryByText("Source added")).not.toBeInTheDocument();

    fireEvent.click(checkbox);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("shows checked state and the already-added chip", () => {
    renderWithClient(
      <ul>
        <PortalSelectCard
          portal={makePortal({ already_added: true, category: "ai" })}
          checked={true}
          onToggle={() => {}}
        />
      </ul>,
    );

    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByText("Source added")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("disables the checkbox when selection is at the cap", () => {
    const onToggle = vi.fn();
    renderWithClient(
      <ul>
        <PortalSelectCard
          portal={makePortal()}
          checked={false}
          disabled={true}
          onToggle={onToggle}
        />
      </ul>,
    );

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeDisabled();
    fireEvent.click(checkbox);
    expect(onToggle).not.toHaveBeenCalled();
  });
});
