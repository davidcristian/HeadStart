import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "./ResetPasswordPage";

// Current value returned by the mocked useSearchParams().get("token").
// `null` means the param is absent (mirrors URLSearchParams.get).
let tokenParam: string | null = "tok-123";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useSearchParams: () => [
      { get: (key: string) => (key === "token" ? tokenParam : null) } as URLSearchParams,
      vi.fn(),
    ],
  };
});

const resetPassword = vi.fn(async (_token: string, _password: string) => ({
  message: "Password updated.",
}));

vi.mock("../api", () => ({
  api: { resetPassword: (token: string, password: string) => resetPassword(token, password) },
}));

function renderPage(token: string | null = "tok-123") {
  tokenParam = token;
  const result = render(
    <MemoryRouter>
      <ResetPasswordPage />
    </MemoryRouter>,
  );
  const inputs = result.container.querySelectorAll("input");
  return {
    ...result,
    passwordInput: inputs[0] as HTMLInputElement,
    confirmInput: inputs[1] as HTMLInputElement,
  };
}

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    tokenParam = "tok-123";
    resetPassword.mockReset();
    resetPassword.mockResolvedValue({ message: "Password updated." });
  });

  it("renders the form when a token is present", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Choose a new password" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update password" })).toBeInTheDocument();
  });

  it("shows an invalid-link banner and no form when the token is missing", () => {
    renderPage(null);
    expect(screen.getByText(/This reset link is invalid\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update password" })).not.toBeInTheDocument();
  });

  it("errors on submit when passwords do not match", async () => {
    const { passwordInput, confirmInput } = renderPage();

    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.change(confirmInput, { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("errors on submit when the token disappears before the request", async () => {
    const { container, passwordInput, confirmInput } = renderPage();

    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.change(confirmInput, { target: { value: "password123" } });
    // The reset token is gone by the time the form is submitted.
    tokenParam = null;
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(
      await screen.findByText("Reset link is missing or invalid. Request a new one."),
    ).toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("resets the password and shows the success message + sign-in link", async () => {
    const { passwordInput, confirmInput } = renderPage();

    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.change(confirmInput, { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Password updated.")).toBeInTheDocument();
    await waitFor(() => expect(resetPassword).toHaveBeenCalledWith("tok-123", "password123"));
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update password" })).not.toBeInTheDocument();
  });

  it("shows the error message when the reset call fails", async () => {
    resetPassword.mockRejectedValue(new Error("Token expired."));
    const { passwordInput, confirmInput } = renderPage();

    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.change(confirmInput, { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Token expired.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a new reset link" })).toBeInTheDocument();
  });

  it("disables the button and shows a busy label while submitting", async () => {
    let resolve: (value: { message: string }) => void = () => {};
    resetPassword.mockImplementation(() => new Promise((r) => (resolve = r)));
    const { passwordInput, confirmInput } = renderPage();

    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.change(confirmInput, { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    const busyButton = await screen.findByRole("button", { name: "Updating..." });
    expect(busyButton).toBeDisabled();

    resolve({ message: "Done." });
    expect(await screen.findByText("Done.")).toBeInTheDocument();
  });
});
