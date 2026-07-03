import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsInboxFastmailForm } from "./SettingsInboxFastmailForm";
import type { FastmailConfig } from "../../types";

const baseConfig: FastmailConfig = {
  email_address: "",
  api_token: "",
};

function renderForm(overrides: Partial<Parameters<typeof SettingsInboxFastmailForm>[0]> = {}) {
  const onChange = vi.fn();
  const onSave = vi.fn();
  const props = {
    fastmailConfig: baseConfig,
    busy: false,
    onChange,
    onSave,
    ...overrides,
  };
  render(<SettingsInboxFastmailForm {...props} />);
  return { onChange, onSave };
}

describe("SettingsInboxFastmailForm", () => {
  it("renders both fields and the save button", () => {
    renderForm();
    expect(screen.getByText("Fastmail email")).toBeInTheDocument();
    expect(screen.getByText("Fastmail API token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Fastmail credentials" })).toBeEnabled();
  });

  it("emits config updates when the email changes", () => {
    const { onChange } = renderForm();
    const emailInput = screen.getByText("Fastmail email").parentElement!.querySelector("input")!;
    fireEvent.change(emailInput, { target: { value: "me@fastmail.com" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, email_address: "me@fastmail.com" });
  });

  it("emits config updates when the api token changes", () => {
    const { onChange } = renderForm();
    const tokenInput = screen
      .getByText("Fastmail API token")
      .parentElement!.querySelector("input")!;
    fireEvent.change(tokenInput, { target: { value: "tok-123" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, api_token: "tok-123" });
  });

  it("calls onSave when the save button is clicked", () => {
    const { onSave } = renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Save Fastmail credentials" }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("disables the save button while busy", () => {
    renderForm({ busy: true });
    expect(screen.getByRole("button", { name: "Save Fastmail credentials" })).toBeDisabled();
  });
});
