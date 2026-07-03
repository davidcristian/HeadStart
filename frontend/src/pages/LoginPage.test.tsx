import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Health, User } from "../types";
import { renderWithClient } from "../test/renderWithClient";
import { LoginPage } from "./LoginPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const login = vi.fn();
let currentUser: User | null = null;

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, login }),
}));

const sampleHealth: Health = { status: "ok", version: "1.0.0", environment: "test" };
const health = vi.fn(async (): Promise<Health> => sampleHealth);

vi.mock("../api", () => ({ api: { health: () => health() } }));

const sampleUser: User = {
  id: 1,
  email: "user@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

function renderPage() {
  const result = renderWithClient(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  const inputs = result.container.querySelectorAll("input");
  return {
    ...result,
    emailInput: inputs[0] as HTMLInputElement,
    passwordInput: inputs[1] as HTMLInputElement,
  };
}

function fillForm(fields: { emailInput: HTMLElement; passwordInput: HTMLElement }) {
  fireEvent.change(fields.emailInput, { target: { value: "user@example.com" } });
  fireEvent.change(fields.passwordInput, { target: { value: "password123" } });
}

describe("LoginPage", () => {
  beforeEach(() => {
    navigate.mockReset();
    login.mockReset();
    login.mockResolvedValue(undefined);
    health.mockReset();
    health.mockResolvedValue(sampleHealth);
    currentUser = null;
  });

  it("renders the sign-in form", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Sign in to HeadStart" })).toBeInTheDocument();
    await waitFor(() => expect(health).toHaveBeenCalled());
  });

  it("redirects an authenticated user to /app", () => {
    currentUser = sampleUser;
    renderPage();
    expect(screen.queryByRole("heading", { name: "Sign in to HeadStart" })).not.toBeInTheDocument();
  });

  it("shows an API-unreachable banner when health check fails", async () => {
    health.mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("API unreachable. Check the URL on the Settings screen."),
    ).toBeInTheDocument();
  });

  it("logs in and navigates to /app on success", async () => {
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("user@example.com", "password123"));
    expect(navigate).toHaveBeenCalledWith("/app", { replace: true });
  });

  it("shows the error message when login fails", async () => {
    login.mockRejectedValue(new Error("Invalid credentials."));
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid credentials.")).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("disables the button and shows a busy label while submitting", async () => {
    let resolve: () => void = () => {};
    login.mockImplementation(() => new Promise<void>((r) => (resolve = r)));
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const busyButton = await screen.findByRole("button", { name: "Signing in..." });
    expect(busyButton).toBeDisabled();

    resolve();
    await waitFor(() => expect(navigate).toHaveBeenCalled());
  });
});
