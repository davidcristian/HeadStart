import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "../types";
import { VerifyEmailPage } from "./VerifyEmailPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const verifyEmail = vi.fn(async (_token: string) => ({ message: "verified" }));
const resendVerificationEmail = vi.fn(async () => ({ message: "Verification email sent." }));

vi.mock("../api", () => ({
  api: {
    verifyEmail: (token: string) => verifyEmail(token),
    resendVerificationEmail: () => resendVerificationEmail(),
  },
}));

const refreshUser = vi.fn(async () => undefined);
let currentUser: User | null = null;
let currentLoading = false;

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, loading: currentLoading, refreshUser }),
}));

const unverifiedUser: User = {
  id: 1,
  email: "user@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: null,
  email_verified_at: null,
  created_at: "2026-06-28T00:00:00Z",
};

function renderPage(initialEntry = "/verify-email") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <VerifyEmailPage />
    </MemoryRouter>,
  );
}

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    navigate.mockReset();
    verifyEmail.mockReset();
    verifyEmail.mockResolvedValue({ message: "verified" });
    resendVerificationEmail.mockReset();
    resendVerificationEmail.mockResolvedValue({ message: "Verification email sent." });
    refreshUser.mockReset();
    refreshUser.mockResolvedValue(undefined);
    currentUser = null;
    currentLoading = false;
  });

  it("prompts an anonymous visitor without a token to sign in", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Verify your email" })).toBeInTheDocument();
    expect(screen.getByText(/Open the verification link from your email/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "sign in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to sign in" })).toBeInTheDocument();
  });

  it("shows the resend form for a signed-in unverified user", () => {
    currentUser = unverifiedUser;
    renderPage();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend verification email" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage your account" })).toBeInTheDocument();
  });

  it("redirects a verified user to /app", () => {
    currentUser = { ...unverifiedUser, email_verified_at: "2026-06-28T00:00:00Z" };
    renderPage();
    expect(screen.queryByRole("heading", { name: "Verify your email" })).not.toBeInTheDocument();
  });

  it("does not redirect a verified user while auth is still loading", () => {
    currentUser = { ...unverifiedUser, email_verified_at: "2026-06-28T00:00:00Z" };
    currentLoading = true;
    renderPage();
    expect(screen.getByRole("heading", { name: "Verify your email" })).toBeInTheDocument();
  });

  it("resends the verification email and shows the success message", async () => {
    currentUser = unverifiedUser;
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByText("Verification email sent.")).toBeInTheDocument();
    expect(resendVerificationEmail).toHaveBeenCalled();
  });

  it("shows an error when resending fails", async () => {
    currentUser = unverifiedUser;
    resendVerificationEmail.mockRejectedValue(new Error("Try again later."));
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByText("Try again later.")).toBeInTheDocument();
  });

  it("disables the resend button and shows a busy label while sending", async () => {
    currentUser = unverifiedUser;
    let resolve: (value: { message: string }) => void = () => {};
    resendVerificationEmail.mockImplementation(() => new Promise((r) => (resolve = r)));
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Resend verification email" }));

    const busyButton = await screen.findByRole("button", { name: "Sending..." });
    expect(busyButton).toBeDisabled();

    resolve({ message: "Done." });
    expect(await screen.findByText("Done.")).toBeInTheDocument();
  });

  it("verifies from a link and navigates to onboarding (anonymous)", async () => {
    renderPage("/verify-email?token=tok-123");

    await waitFor(() => expect(verifyEmail).toHaveBeenCalledWith("tok-123"));
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/app/onboarding", { replace: true }),
    );
    expect(refreshUser).not.toHaveBeenCalled();
  });

  it("refreshes the current user when verifying from a link while signed in", async () => {
    currentUser = unverifiedUser;
    renderPage("/verify-email?token=tok-123");

    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/app/onboarding", { replace: true }),
    );
  });

  it("shows an error when link verification fails", async () => {
    verifyEmail.mockRejectedValue(new Error("Invalid or expired token."));
    renderPage("/verify-email?token=bad");

    expect(await screen.findByText("Invalid or expired token.")).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("shows the confirming state while a token verification is in flight", async () => {
    let resolve: (value: { message: string }) => void = () => {};
    verifyEmail.mockImplementation(() => new Promise((r) => (resolve = r)));
    renderPage("/verify-email?token=tok-123");

    expect(screen.getByText("Confirming your email address...")).toBeInTheDocument();

    resolve({ message: "verified" });
    await waitFor(() => expect(navigate).toHaveBeenCalled());
  });

  it("ignores a resolved verification after unmount (cancelled cleanup)", async () => {
    let resolve: (value: { message: string }) => void = () => {};
    verifyEmail.mockImplementation(() => new Promise((r) => (resolve = r)));
    const { unmount } = renderPage("/verify-email?token=tok-123");

    unmount();
    resolve({ message: "verified" });
    await Promise.resolve();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("ignores a rejected verification after unmount (cancelled cleanup)", async () => {
    let reject: (reason: Error) => void = () => {};
    verifyEmail.mockImplementation(() => new Promise((_r, rej) => (reject = rej)));
    const { unmount } = renderPage("/verify-email?token=tok-123");

    unmount();
    reject(new Error("late failure"));
    await Promise.resolve();
    expect(screen.queryByText("late failure")).not.toBeInTheDocument();
  });
});
