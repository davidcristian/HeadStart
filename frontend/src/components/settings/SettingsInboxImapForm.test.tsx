import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsInboxImapForm } from "./SettingsInboxImapForm";
import type { MailboxConfig } from "../../types";

const baseConfig: MailboxConfig = {
  imap_host: "imap.example.com",
  imap_user: "user@example.com",
  imap_password: "",
  smtp_host: "smtp.example.com",
  smtp_password: "",
  smtp_from: "",
};

function renderForm(overrides: Partial<Parameters<typeof SettingsInboxImapForm>[0]> = {}) {
  const onChange = vi.fn();
  const onSave = vi.fn();
  const onTest = vi.fn();
  const onDisconnect = vi.fn();
  const props = {
    imapConfig: baseConfig,
    busy: false,
    hasCredential: false,
    onChange,
    onSave,
    onTest,
    onDisconnect,
    ...overrides,
  };
  render(<SettingsInboxImapForm {...props} />);
  return { onChange, onSave, onTest, onDisconnect };
}

function inputFor(label: string): HTMLInputElement {
  return screen.getByText(label).parentElement!.querySelector("input")!;
}

describe("SettingsInboxImapForm", () => {
  it("renders every field", () => {
    renderForm();
    expect(screen.getByText("IMAP host")).toBeInTheDocument();
    expect(screen.getByText("IMAP user")).toBeInTheDocument();
    expect(screen.getByText("IMAP password")).toBeInTheDocument();
    expect(screen.getByText("SMTP host")).toBeInTheDocument();
    expect(screen.getByText("SMTP password")).toBeInTheDocument();
  });

  it("emits updates for each editable field", () => {
    const { onChange } = renderForm();

    fireEvent.change(inputFor("IMAP host"), { target: { value: "imap.new" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, imap_host: "imap.new" });

    fireEvent.change(inputFor("IMAP user"), { target: { value: "new@user" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, imap_user: "new@user" });

    fireEvent.change(inputFor("IMAP password"), { target: { value: "pw" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, imap_password: "pw" });

    fireEvent.change(inputFor("SMTP host"), { target: { value: "smtp.new" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, smtp_host: "smtp.new" });

    fireEvent.change(inputFor("SMTP password"), { target: { value: "spw" } });
    expect(onChange).toHaveBeenCalledWith({ ...baseConfig, smtp_password: "spw" });
  });

  it("wires the save and test buttons", () => {
    const { onSave, onTest } = renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Save IMAP credentials" }));
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onTest).toHaveBeenCalledTimes(1);
  });

  it("hides the disconnect button without a credential", () => {
    renderForm({ hasCredential: false });
    expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
  });

  it("shows and wires the disconnect button when a credential exists", () => {
    const { onDisconnect } = renderForm({ hasCredential: true });
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it("disables the action buttons while busy", () => {
    renderForm({ busy: true, hasCredential: true });
    expect(screen.getByRole("button", { name: "Save IMAP credentials" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Test connection" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeDisabled();
  });
});
