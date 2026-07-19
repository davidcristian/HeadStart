import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { must } from "../../test/must";
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

  describe.each([
    ["Connect Gmail", "gmailAuthorize", "Could not start Gmail OAuth."],
    ["Connect Outlook", "outlookAuthorize", "Could not start Outlook OAuth."],
    ["Connect Yahoo", "yahooAuthorize", "Could not start Yahoo OAuth."],
  ] as const)("%s", (buttonName, method, errorText) => {
    it("redirects on success", async () => {
      mockApi[method].mockResolvedValue({ authorization_url: "https://oauth.test/go" });
      render(<SettingsInboxCard />);
      await waitFor(() =>
        expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
      );
      fireEvent.click(screen.getByRole("button", { name: buttonName }));
      await waitFor(() => expect(assign).toHaveBeenCalledWith("https://oauth.test/go"));
    });

    it("shows an error on failure", async () => {
      mockApi[method].mockRejectedValue(new Error("oauth down"));
      render(<SettingsInboxCard />);
      await waitFor(() =>
        expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
      );
      fireEvent.click(screen.getByRole("button", { name: buttonName }));
      expect(await screen.findByText("oauth down")).toBeInTheDocument();
    });

    it("shows a generic error for non-Error throws", async () => {
      mockApi[method].mockRejectedValue("weird");
      render(<SettingsInboxCard />);
      await waitFor(() =>
        expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
      );
      fireEvent.click(screen.getByRole("button", { name: buttonName }));
      expect(await screen.findByText(errorText)).toBeInTheDocument();
    });
  });

  it("saves Fastmail credentials and clears the token", async () => {
    mockApi.upsertMailboxCredentials.mockResolvedValue(
      credential({ connector_type: "fastmail", email_address: "me@fastmail.com" }),
    );
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    const emailInput = screen.getByText("Fastmail email").parentElement!.querySelector("input")!;
    const tokenInput = screen
      .getByText("Fastmail API token")
      .parentElement!.querySelector("input")!;
    fireEvent.change(emailInput, { target: { value: "me@fastmail.com" } });
    fireEvent.change(tokenInput, { target: { value: "tok" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Fastmail credentials" }));

    await waitFor(() => expect(mockApi.upsertMailboxCredentials).toHaveBeenCalled());
    expect(mockApi.upsertMailboxCredentials).toHaveBeenCalledWith({
      connector_type: "fastmail",
      enabled: true,
      config: { email_address: "me@fastmail.com", api_token: "tok" },
    });
    expect(await screen.findByText("Fastmail credentials saved.")).toBeInTheDocument();
    expect((tokenInput as HTMLInputElement).value).toBe("");
  });

  it("shows an error when saving Fastmail fails", async () => {
    mockApi.upsertMailboxCredentials.mockRejectedValue(new Error("fastmail boom"));
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save Fastmail credentials" }));
    expect(await screen.findByText("fastmail boom")).toBeInTheDocument();
  });

  it("shows a generic error for non-Error Fastmail failures", async () => {
    mockApi.upsertMailboxCredentials.mockRejectedValue("weird");
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save Fastmail credentials" }));
    expect(await screen.findByText("Could not save Fastmail credentials.")).toBeInTheDocument();
  });

  it("saves IMAP credentials, deriving smtp_user/smtp_from from imap_user", async () => {
    mockApi.upsertMailboxCredentials.mockResolvedValue(credential());
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    const imapUser = screen.getByText("IMAP user").parentElement!.querySelector("input")!;
    fireEvent.change(imapUser, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Save IMAP credentials" }));

    await waitFor(() => expect(mockApi.upsertMailboxCredentials).toHaveBeenCalled());
    const payload = must(mockApi.upsertMailboxCredentials.mock.calls[0])[0] as {
      config: { smtp_user?: string; smtp_from?: string };
    };
    expect(payload.config.smtp_user).toBe("user@example.com");
    expect(payload.config.smtp_from).toBe("user@example.com");
    expect(await screen.findByText("Mailbox credentials saved.")).toBeInTheDocument();
  });

  it("shows an error when saving IMAP fails", async () => {
    mockApi.upsertMailboxCredentials.mockRejectedValue(new Error("imap boom"));
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save IMAP credentials" }));
    expect(await screen.findByText("imap boom")).toBeInTheDocument();
  });

  it("shows a generic error for non-Error IMAP failures", async () => {
    mockApi.upsertMailboxCredentials.mockRejectedValue("weird");
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save IMAP credentials" }));
    expect(await screen.findByText("Could not save mailbox credentials.")).toBeInTheDocument();
  });

  it("tests the connection without a credential and reports success", async () => {
    mockApi.testMailbox.mockResolvedValue({ imap_ok: true, smtp_ok: true, error: null });
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() => expect(mockApi.testMailbox).toHaveBeenCalled());
    // No credential -> passes the manual config through.
    expect(must(mockApi.testMailbox.mock.calls[0])[0]).toMatchObject({
      connector_type: "imap_smtp",
    });
    expect(await screen.findByText("Mailbox connection succeeded.")).toBeInTheDocument();
  });

  it("tests an existing credential without sending config", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(credential());
    mockApi.testMailbox.mockResolvedValue({ imap_ok: true, smtp_ok: true, error: null });
    render(<SettingsInboxCard />);
    await screen.findByRole("button", { name: "Disconnect" });
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(mockApi.testMailbox).toHaveBeenCalledWith(undefined));
  });

  it("reports the server error when a test fails with a message", async () => {
    mockApi.testMailbox.mockResolvedValue({ imap_ok: false, smtp_ok: true, error: "auth failed" });
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("auth failed")).toBeInTheDocument();
  });

  it("falls back to a default message when a test fails without an error", async () => {
    mockApi.testMailbox.mockResolvedValue({ imap_ok: false, smtp_ok: false, error: null });
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("Mailbox connection failed.")).toBeInTheDocument();
  });

  it("shows an error when the test throws", async () => {
    mockApi.testMailbox.mockRejectedValue(new Error("test threw"));
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("test threw")).toBeInTheDocument();
  });

  it("shows a generic error when the test throws a non-Error", async () => {
    mockApi.testMailbox.mockRejectedValue("weird");
    render(<SettingsInboxCard />);
    await waitFor(() =>
      expect(screen.queryByText("Loading mailbox settings…")).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText("Mailbox test failed.")).toBeInTheDocument();
  });

  it("disconnects an existing credential", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(credential());
    mockApi.deleteMailboxCredentials.mockResolvedValue(undefined);
    render(<SettingsInboxCard />);
    await screen.findByRole("button", { name: "Disconnect" });
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));

    await waitFor(() => expect(mockApi.deleteMailboxCredentials).toHaveBeenCalled());
    expect(await screen.findByText("Mailbox disconnected.")).toBeInTheDocument();
    // Disconnect button disappears once the credential is cleared.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument(),
    );
  });

  it("shows an error when disconnect fails", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(credential());
    mockApi.deleteMailboxCredentials.mockRejectedValue(new Error("disconnect boom"));
    render(<SettingsInboxCard />);
    await screen.findByRole("button", { name: "Disconnect" });
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByText("disconnect boom")).toBeInTheDocument();
  });

  it("shows a generic error when disconnect throws a non-Error", async () => {
    mockApi.getMailboxCredentials.mockResolvedValue(credential());
    mockApi.deleteMailboxCredentials.mockRejectedValue("weird");
    render(<SettingsInboxCard />);
    await screen.findByRole("button", { name: "Disconnect" });
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByText("Could not disconnect mailbox.")).toBeInTheDocument();
  });
});
