import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "../types";
import { RegisterPage } from "./RegisterPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const register = vi.fn();
let currentUser: User | null = null;

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, register }),
}));

const sampleUser: User = {
  id: 1,
  email: "new@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: null,
  email_verified_at: null,
  created_at: "2026-06-28T00:00:00Z",
};

function renderPage() {
  const result = render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  );
  const inputs = result.container.querySelectorAll("input");
  return {
    ...result,
    emailInput: inputs[0] as HTMLInputElement,
    passwordInput: inputs[1] as HTMLInputElement,
    confirmInput: inputs[2] as HTMLInputElement,
  };
}

function fillForm(
  fields: { emailInput: HTMLElement; passwordInput: HTMLElement; confirmInput: HTMLElement },
  {
    password = "password123",
    confirm = "password123",
  }: { password?: string; confirm?: string } = {},
) {
  fireEvent.change(fields.emailInput, { target: { value: "a@b.test" } });
  fireEvent.change(fields.passwordInput, { target: { value: password } });
  fireEvent.change(fields.confirmInput, { target: { value: confirm } });
}

describe("RegisterPage", () => {
  beforeEach(() => {
    navigate.mockReset();
    register.mockReset();
    register.mockResolvedValue(undefined);
    currentUser = null;
  });

  it("renders the registration form", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: "Create your HeadStart account" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("redirects an authenticated user to /app", () => {
    currentUser = sampleUser;
    renderPage();
    expect(
      screen.queryByRole("heading", { name: "Create your HeadStart account" }),
    ).not.toBeInTheDocument();
  });

  it("shows an error when passwords do not match", async () => {
    const fields = renderPage();

    fillForm(fields, { confirm: "different" });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it("registers and navigates to /verify-email on success", async () => {
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(register).toHaveBeenCalledWith("a@b.test", "password123"));
    expect(navigate).toHaveBeenCalledWith("/verify-email", { replace: true });
  });

  it("shows the error message when registration fails", async () => {
    register.mockRejectedValue(new Error("Too many requests. Try again later."));
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Too many requests. Try again later.")).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("disables the button and shows a busy label while submitting", async () => {
    let resolve: () => void = () => {};
    register.mockImplementation(() => new Promise<void>((r) => (resolve = r)));
    const fields = renderPage();

    fillForm(fields);
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    const busyButton = await screen.findByRole("button", { name: "Creating..." });
    expect(busyButton).toBeDisabled();

    resolve();
    await waitFor(() => expect(navigate).toHaveBeenCalled());
  });
});
