import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { User } from "../types";
import { mockApi, resetMockApi } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { OnboardingPage } from "./OnboardingPage";

const baseUser: User = {
  id: 1,
  email: "new@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: null,
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

const authState = vi.hoisted(() => ({
  user: null as User | null,
  refreshUser: vi.fn(async () => undefined),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => authState,
}));

function renderPage() {
  return renderWithClient(
    <MemoryRouter initialEntries={["/app/onboarding"]}>
      <Routes>
        <Route path="/app/onboarding" element={<OnboardingPage />} />
        <Route path="/app/searches" element={<div>SEARCHES SENTINEL</div>} />
        <Route path="/app/jobs" element={<div>JOBS SENTINEL</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("OnboardingPage branch coverage", () => {
  beforeEach(() => {
    resetMockApi();
    authState.user = { ...baseUser };
    authState.refreshUser.mockClear();
  });

  it("redirects to searches when onboarding is already complete", () => {
    authState.user = { ...baseUser, onboarding_completed_at: "2026-06-29T00:00:00Z" };
    renderPage();

    expect(screen.getByText("SEARCHES SENTINEL")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome to HeadStart" })).not.toBeInTheDocument();
  });

  it("renders the wizard when the user is unauthenticated (null)", () => {
    authState.user = null;
    renderPage();

    expect(screen.getByRole("heading", { name: "Welcome to HeadStart" })).toBeInTheDocument();
  });

  it("walks every step, exercising back buttons, detect notice, and run/complete", async () => {
    renderPage();

    // Welcome -> Source
    fireEvent.click(screen.getByRole("button", { name: "Get started" }));
    expect(screen.getByRole("heading", { name: "Add a job board" })).toBeInTheDocument();

    // Source: Back returns to welcome (SourceStep onBack).
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Welcome to HeadStart" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Get started" }));

    // Detect board fills fields and shows an info notice banner (SourceStep onDetect).
    fireEvent.change(screen.getByLabelText("Careers or search URL"), {
      target: { value: "https://boards.greenhouse.io/acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Detect board" }));
    await waitFor(() => expect(mockApi.detectSource).toHaveBeenCalled());
    expect(screen.getByText("Detected greenhouse board for ACME Careers.")).toBeInTheDocument();

    // Submit source -> Target step.
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Where should alerts go?" })).toBeInTheDocument(),
    );

    // Target: Back returns to source (TargetStep onBack), then continue again.
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Add a job board" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Where should alerts go?" })).toBeInTheDocument(),
    );

    // Fill the required ntfy topic so the target form can submit.
    fireEvent.change(screen.getByLabelText("ntfy topic", { exact: false }), {
      target: { value: "my-job-alerts" },
    });

    // Submit target -> Search step (TargetStep onSubmit).
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Create your first search" })).toBeInTheDocument(),
    );
    expect(mockApi.createTarget).toHaveBeenCalled();

    // Search: Back returns to target (SearchStep onBack), then continue again.
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Where should alerts go?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Create your first search" })).toBeInTheDocument(),
    );

    // Submit search -> Run step (SearchStep onSubmit).
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Run your first check" })).toBeInTheDocument(),
    );
    expect(mockApi.createSearch).toHaveBeenCalled();

    // Run now (RunStep onRun) -> success notice banner.
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));
    await waitFor(() => expect(mockApi.runSearch).toHaveBeenCalled());
    expect(screen.getByText(/Found 3 posting/)).toBeInTheDocument();

    // Go to Jobs (RunStep onComplete) -> completes onboarding and navigates.
    fireEvent.click(screen.getByRole("button", { name: "Go to Jobs" }));
    await waitFor(() => expect(mockApi.completeOnboarding).toHaveBeenCalled());
    expect(screen.getByText("JOBS SENTINEL")).toBeInTheDocument();
  });

  it("shows an error banner when creating the source fails", async () => {
    mockApi.createSource.mockRejectedValueOnce(new Error("source blew up"));
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Get started" }));
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "ACME Careers" },
    });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://boards.greenhouse.io/acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(screen.getByText("source blew up")).toBeInTheDocument());
  });
});
