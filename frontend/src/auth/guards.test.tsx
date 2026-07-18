import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { User } from "../types";
import { AdminRoute } from "./AdminRoute";
import { EmailVerificationGuard } from "./EmailVerificationGuard";
import { OnboardingGuard } from "./OnboardingGuard";

vi.mock("./AuthContext", () => ({ useAuth: vi.fn() }));
import { useAuth } from "./AuthContext";

const mockUseAuth = vi.mocked(useAuth);
type AuthValue = ReturnType<typeof useAuth>;

function authState(overrides: Partial<AuthValue>): AuthValue {
  return {
    user: null,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    ...overrides,
  };
}

const baseUser: User = {
  id: 1,
  email: "a@b.test",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

function renderGuard(guard: ReactElement): ReturnType<typeof render> {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route element={guard}>
          <Route path="/protected" element={<div>protected content</div>} />
        </Route>
        <Route path="/verify-email" element={<div>verify screen</div>} />
        <Route path="/app/onboarding" element={<div>onboarding screen</div>} />
        <Route path="/app/searches" element={<div>searches screen</div>} />
        <Route path="/login" element={<div>login screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("EmailVerificationGuard", () => {
  it("shows a loading state while auth is resolving", () => {
    mockUseAuth.mockReturnValue(authState({ user: null, loading: true }));
    renderGuard(<EmailVerificationGuard />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to /login", () => {
    mockUseAuth.mockReturnValue(authState({ user: null }));
    renderGuard(<EmailVerificationGuard />);
    expect(screen.getByText("login screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects unverified accounts to /verify-email", () => {
    mockUseAuth.mockReturnValue(authState({ user: { ...baseUser, email_verified_at: null } }));
    renderGuard(<EmailVerificationGuard />);
    expect(screen.getByText("verify screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("renders the protected outlet for verified accounts", () => {
    mockUseAuth.mockReturnValue(authState({ user: baseUser }));
    renderGuard(<EmailVerificationGuard />);
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });
});

describe("OnboardingGuard", () => {
  it("shows a loading state while auth is resolving", () => {
    mockUseAuth.mockReturnValue(authState({ user: null, loading: true }));
    renderGuard(<OnboardingGuard />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to /login", () => {
    mockUseAuth.mockReturnValue(authState({ user: null }));
    renderGuard(<OnboardingGuard />);
    expect(screen.getByText("login screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects accounts that have not finished onboarding to /app/onboarding", () => {
    mockUseAuth.mockReturnValue(
      authState({ user: { ...baseUser, onboarding_completed_at: null } }),
    );
    renderGuard(<OnboardingGuard />);
    expect(screen.getByText("onboarding screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("renders the protected outlet once onboarding is complete", () => {
    mockUseAuth.mockReturnValue(authState({ user: baseUser }));
    renderGuard(<OnboardingGuard />);
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });
});

describe("AdminRoute", () => {
  it("shows a loading state while auth is resolving", () => {
    mockUseAuth.mockReturnValue(authState({ user: null, loading: true }));
    renderGuard(<AdminRoute />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to /login", () => {
    mockUseAuth.mockReturnValue(authState({ user: null }));
    renderGuard(<AdminRoute />);
    expect(screen.getByText("login screen")).toBeInTheDocument();
  });

  it("redirects non-admins to /app/searches", () => {
    mockUseAuth.mockReturnValue(authState({ user: { ...baseUser, is_admin: false } }));
    renderGuard(<AdminRoute />);
    expect(screen.getByText("searches screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("renders the protected outlet for admins", () => {
    mockUseAuth.mockReturnValue(authState({ user: { ...baseUser, is_admin: true } }));
    renderGuard(<AdminRoute />);
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });
});
