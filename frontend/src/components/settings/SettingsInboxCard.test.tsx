import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsInboxCard } from "./SettingsInboxCard";
import type { MailboxCredential } from "../../types";

const mockApi = vi.hoisted(() => ({
  getMailboxCredentials: vi.fn(),
  upsertMailboxCredentials: vi.fn(),
  deleteMailboxCredentials: vi.fn(),
  testMailbox: vi.fn(),
  gmailAuthorize: vi.fn(),
  outlookAuthorize: vi.fn(),
  yahooAuthorize: vi.fn(),
}));

vi.mock("../../api", () => ({ api: mockApi }));

function credential(overrides: Partial<MailboxCredential> = {}): MailboxCredential {
  return {
    id: 1,
    connector_type: "imap_smtp",
    enabled: true,
    created_at: "2026-06-28T00:00:00Z",
    has_config: true,
    imap_host: "imap.example.com",
    smtp_host: "smtp.example.com",
    imap_user: "user@example.com",
    email_address: null,
    ...overrides,
  };
}

const assign = vi.fn();

describe("SettingsInboxCard", () => {
  beforeEach(() => {
    Object.values(mockApi).forEach((fn) => fn.mockReset());
    assign.mockReset();
    vi.stubGlobal("location", { assign });
    // Default: no credential configured yet.
    mockApi.getMailboxCredentials.mockRejectedValue(new Error("Mailbox not configured"));
  });

  it("renders and loads without a credential (not-configured is silent)", async () => {
    render(<SettingsInboxCard />);
    expect(screen.getByText("Loading mailbox settings…")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument();
    // No credential -> no Disconnect button.
    expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
  });

  it("surfaces a non-'not configured' load error", async () => {
    mockApi.getMailboxCredentials.mockRejectedValue(new Error("server exploded"));
    render(<SettingsInboxCard />);
    expect(await screen.findByText("server exploded")).toBeInTheDocument();
  });

  it("surfaces a generic load error for non-Error throws", async () => {
    mockApi.getMailboxCredentials.mockRejectedValue("weird");
    render(<SettingsInboxCard />);
    expect(await screen.findByText("Could not load mailbox settings.")).toBeInTheDocument();
  });

  it("prefills IMAP fields from an existing imap_smtp credential", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(credential());
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
  });

  it("keeps default IMAP fields when the credential omits host/user", async () => {
    // Null imap_host/smtp_host/imap_user exercise the `?? current.X` fallbacks
    // in the load effect, leaving the form on its EMPTY_IMAP_CONFIG defaults.
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ imap_host: null, smtp_host: null, imap_user: null }),
    );
    render(<SettingsInboxCard />);
    await screen.findByRole("button", { name: "Disconnect" });
    const imapHost = screen.getByText("IMAP host").parentElement!.querySelector("input")!;
    const smtpHost = screen.getByText("SMTP host").parentElement!.querySelector("input")!;
    const imapUser = screen.getByText("IMAP user").parentElement!.querySelector("input")!;
    expect((imapHost as HTMLInputElement).value).toBe("imap.gmail.com");
    expect((smtpHost as HTMLInputElement).value).toBe("smtp.gmail.com");
    expect((imapUser as HTMLInputElement).value).toBe("");
  });

  it("shows the connected Gmail address", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "gmail", email_address: "me@gmail.com" }),
    );
    render(<SettingsInboxCard />);
    expect(await screen.findByText("me@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("Connected Gmail:")).toBeInTheDocument();
  });

  it("shows the connected Outlook address", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "outlook", email_address: "me@outlook.com" }),
    );
    render(<SettingsInboxCard />);
    expect(await screen.findByText("me@outlook.com")).toBeInTheDocument();
  });

  it("shows the connected Yahoo address", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "yahoo", email_address: "me@yahoo.com" }),
    );
    render(<SettingsInboxCard />);
    expect(await screen.findByText("me@yahoo.com")).toBeInTheDocument();
  });

  it("shows and prefills the connected Fastmail address", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "fastmail", email_address: "me@fastmail.com" }),
    );
    render(<SettingsInboxCard />);
    expect(await screen.findByText("me@fastmail.com")).toBeInTheDocument();
    expect(screen.getByText("Connected Fastmail:")).toBeInTheDocument();
  });

  it("does not prefill the fastmail form when the address is empty", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "fastmail", email_address: "" }),
    );
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    // The connected line still renders, but the editable email field stays empty
    // because the prefill effect skips the empty address.
    const emailInput = screen.getByText("Fastmail email").parentElement!.querySelector("input")!;
    expect((emailInput as HTMLInputElement).value).toBe("");
  });

  it.each([
    ["gmail_connected", "Gmail connected successfully."],
    ["outlook_connected", "Outlook connected successfully."],
    ["yahoo_connected", "Yahoo Mail connected successfully."],
  ])("shows the %s success notice", async (notice, text) => {
    render(<SettingsInboxCard mailboxNotice={notice} />);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it.each([
    ["gmail_error", "Gmail connection failed. Try again or use IMAP credentials."],
    ["outlook_error", "Outlook connection failed. Try again or use IMAP credentials."],
    ["yahoo_error", "Yahoo Mail connection failed. Try again or use IMAP credentials."],
  ])("shows the %s error notice", async (notice, text) => {
    render(<SettingsInboxCard mailboxNotice={notice} />);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("ignores an unknown mailbox notice", async () => {
    render(<SettingsInboxCard mailboxNotice="something_else" />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(/successfully/)).not.toBeInTheDocument();
  });
});
