import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { User } from "../types";
import { ProtectedRoute } from "./ProtectedRoute";

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

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/protected" element={<div>protected content</div>} />
        </Route>
        <Route path="/login" element={<div>login screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("shows a loading state while auth is resolving", () => {
    mockUseAuth.mockReturnValue(authState({ loading: true }));
    renderRoute();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to /login", () => {
    mockUseAuth.mockReturnValue(authState({ user: null }));
    renderRoute();
    expect(screen.getByText("login screen")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("renders the protected outlet for authenticated users", () => {
    mockUseAuth.mockReturnValue(authState({ user: baseUser }));
    renderRoute();
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });
});
