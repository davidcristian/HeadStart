import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    const payload = mockApi.upsertMailboxCredentials.mock.calls[0][0] as {
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
    expect(mockApi.testMailbox.mock.calls[0][0]).toMatchObject({ connector_type: "imap_smtp" });
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
