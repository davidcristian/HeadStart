import { act, render, waitFor } from "@testing-library/react";
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

const credential: MailboxCredential = {
  id: 1,
  connector_type: "imap_smtp",
  enabled: true,
  created_at: "2026-06-28T00:00:00Z",
  has_config: true,
  imap_host: "imap.example.com",
  smtp_host: "smtp.example.com",
  imap_user: "user@example.com",
  email_address: null,
};

describe("SettingsInboxCard (unmount races)", () => {
  beforeEach(() => {
    Object.values(mockApi).forEach((fn) => fn.mockReset());
  });

  it("ignores a credential that resolves after unmount", async () => {
    let resolveCredential!: (value: MailboxCredential) => void;
    mockApi.getMailboxCredentials.mockReturnValue(
      new Promise<MailboxCredential>((resolve) => {
        resolveCredential = resolve;
      }),
    );

    const { container, unmount } = render(<SettingsInboxCard />);
    await waitFor(() => expect(mockApi.getMailboxCredentials).toHaveBeenCalled());
    unmount();
    await act(async () => {
      resolveCredential(credential);
    });

    expect(container).toBeEmptyDOMElement();
  });

  it("ignores a credential failure that lands after unmount", async () => {
    let rejectCredential!: (reason: Error) => void;
    mockApi.getMailboxCredentials.mockReturnValue(
      new Promise<MailboxCredential>((_resolve, reject) => {
        rejectCredential = reject;
      }),
    );

    const { container, unmount } = render(<SettingsInboxCard />);
    await waitFor(() => expect(mockApi.getMailboxCredentials).toHaveBeenCalled());
    unmount();
    await act(async () => {
      rejectCredential(new Error("mailbox unreachable"));
    });

    expect(container).toBeEmptyDOMElement();
  });
});
