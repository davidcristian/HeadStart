import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { NotificationTarget } from "../../types";
import { sampleTarget } from "../../test/fixtures";
import { renderWithClient } from "../../test/renderWithClient";
import { PortalsSubscribeCard } from "./PortalsSubscribeCard";

type Props = Parameters<typeof PortalsSubscribeCard>[0];

function renderCard(overrides: Partial<Props> = {}) {
  const props: Props = {
    targets: [],
    targetId: "",
    setTargetId: vi.fn(),
    interval: 900,
    setInterval: vi.fn(),
    onCreateAlerts: vi.fn(),
    subscribePending: false,
    ...overrides,
  };
  const utils = renderWithClient(
    <MemoryRouter>
      <PortalsSubscribeCard {...props} />
    </MemoryRouter>,
  );
  return { props, ...utils };
}

describe("PortalsSubscribeCard", () => {
  it("prompts to create a target when none exist", () => {
    renderCard({ targets: [] });

    expect(screen.getByRole("link", { name: "Create a notification target" })).toHaveAttribute(
      "href",
      "/app/targets",
    );
  });

  it("lists targets and reacts to selection and interval changes", () => {
    const targets: NotificationTarget[] = [sampleTarget];
    const { props } = renderCard({ targets });

    expect(screen.queryByText("Create a notification target")).not.toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: `${sampleTarget.name} (${sampleTarget.type})` }),
    ).toBeInTheDocument();

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: String(sampleTarget.id) } });
    expect(props.setTargetId).toHaveBeenCalledWith(sampleTarget.id);

    // Choosing the placeholder clears the selection back to "".
    fireEvent.change(select, { target: { value: "" } });
    expect(props.setTargetId).toHaveBeenCalledWith("");

    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "1200" } });
    expect(props.setInterval).toHaveBeenCalledWith(1200);
  });

  it("invokes onCreateAlerts when enabled and shows the pending label when busy", () => {
    const { props, rerender } = renderCard({ targets: [sampleTarget] });

    fireEvent.click(screen.getByRole("button", { name: "Create alerts" }));
    expect(props.onCreateAlerts).toHaveBeenCalledTimes(1);

    rerender(
      <MemoryRouter>
        <PortalsSubscribeCard {...props} subscribePending={true} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: "Creating..." })).toBeDisabled();
  });
});
