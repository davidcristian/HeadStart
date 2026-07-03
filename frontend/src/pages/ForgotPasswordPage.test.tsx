import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

const forgotPassword = vi.fn(async (_email: string) => ({ message: "Check your inbox." }));

vi.mock("../api", () => ({ api: { forgotPassword: (email: string) => forgotPassword(email) } }));

function renderPage() {
  const result = render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
  const emailInput = result.container.querySelector("input") as HTMLInputElement;
  return { ...result, emailInput };
}

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    forgotPassword.mockReset();
    forgotPassword.mockResolvedValue({ message: "Check your inbox." });
  });

  it("renders the request form", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeInTheDocument();
  });

  it("submits and shows the success message, hiding the form", async () => {
    const { emailInput } = renderPage();

    fireEvent.change(emailInput, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Check your inbox.")).toBeInTheDocument();
    await waitFor(() => expect(forgotPassword).toHaveBeenCalledWith("user@example.com"));
    expect(screen.queryByRole("button", { name: "Send reset link" })).not.toBeInTheDocument();
  });

  it("shows the error message when the request fails", async () => {
    forgotPassword.mockRejectedValue(new Error("Rate limited."));
    const { emailInput } = renderPage();

    fireEvent.change(emailInput, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Rate limited.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeInTheDocument();
  });

  it("disables the button and shows a busy label while submitting", async () => {
    let resolve: (value: { message: string }) => void = () => {};
    forgotPassword.mockImplementation(() => new Promise((r) => (resolve = r)));
    const { emailInput } = renderPage();

    fireEvent.change(emailInput, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    const busyButton = await screen.findByRole("button", { name: "Sending..." });
    expect(busyButton).toBeDisabled();

    resolve({ message: "Done." });
    expect(await screen.findByText("Done.")).toBeInTheDocument();
  });
});
