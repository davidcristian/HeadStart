import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../../test/renderWithClient";
import { SearchStep } from "./SearchStep";

type Props = Parameters<typeof SearchStep>[0];

function renderStep(overrides: Partial<Props> = {}) {
  const props: Props = {
    busy: false,
    searchName: "Backend roles",
    queryUrl: "https://boards.greenhouse.io/acme",
    keywords: "engineer backend",
    onSearchNameChange: vi.fn(),
    onQueryUrlChange: vi.fn(),
    onKeywordsChange: vi.fn(),
    onSubmit: vi.fn((e) => e.preventDefault()),
    onBack: vi.fn(),
    ...overrides,
  };
  const utils = renderWithClient(<SearchStep {...props} />);
  return { props, ...utils };
}

describe("SearchStep", () => {
  it("edits every field", () => {
    const { props } = renderStep();

    fireEvent.change(screen.getByLabelText("Search name"), {
      target: { value: "New search" },
    });
    expect(props.onSearchNameChange).toHaveBeenCalledWith("New search");

    fireEvent.change(screen.getByLabelText("Query URL"), {
      target: { value: "https://new.test" },
    });
    expect(props.onQueryUrlChange).toHaveBeenCalledWith("https://new.test");

    fireEvent.change(screen.getByPlaceholderText("engineer backend"), {
      target: { value: "python" },
    });
    expect(props.onKeywordsChange).toHaveBeenCalledWith("python");
  });

  it("submits and goes back", () => {
    const { props } = renderStep();

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(props.onSubmit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(props.onBack).toHaveBeenCalledTimes(1);
  });

  it("disables continue while busy", () => {
    renderStep({ busy: true });
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});
