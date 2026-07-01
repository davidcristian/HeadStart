import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { mockApi, resetMockApi } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { OnboardingPage } from "./OnboardingPage";

const refreshUser = vi.fn(async () => undefined);

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "new@example.com",
      is_admin: false,
      is_active: true,
      onboarding_completed_at: null,
      created_at: "2026-06-28T00:00:00Z",
    },
    refreshUser,
  }),
}));

describe("OnboardingPage", () => {
  beforeEach(() => {
    resetMockApi();
    refreshUser.mockClear();
    mockApi.me.mockResolvedValue({
      id: 1,
      email: "new@example.com",
      is_admin: false,
      is_active: true,
      onboarding_completed_at: null,
      created_at: "2026-06-28T00:00:00Z",
    });
  });

  function renderPage() {
    return renderWithClient(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
  }

  it("shows the welcome step for new users", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Welcome to HeadStart" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get started" })).toBeInTheDocument();
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());
  });

  it("advances through source and target steps", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Get started" }));
    expect(screen.getByRole("heading", { name: "Add a job board" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "ACME Careers" },
    });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://boards.greenhouse.io/acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(mockApi.createSource).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Where should alerts go?" })).toBeInTheDocument();
  });

  it("skips setup and marks onboarding complete", async () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));

    await waitFor(() => expect(mockApi.completeOnboarding).toHaveBeenCalled());
    expect(refreshUser).toHaveBeenCalled();
  });
});
