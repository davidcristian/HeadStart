import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SiteCredential, Source } from "../types";
import { CredentialsPage } from "./CredentialsPage";

const listCredentials = vi.fn(async (): Promise<SiteCredential[]> => []);
const listSources = vi.fn(async (): Promise<Source[]> => []);
const createCredential = vi.fn(async (_data: unknown) => credentialFixture);
const updateCredential = vi.fn(async (_id: number, _data: unknown) => credentialFixture);
const deleteCredential = vi.fn(async (_id: number) => undefined);

vi.mock("../api", () => ({
  api: {
    listCredentials: () => listCredentials(),
    listSources: () => listSources(),
    createCredential: (data: unknown) => createCredential(data),
    updateCredential: (id: number, data: unknown) => updateCredential(id, data),
    deleteCredential: (id: number) => deleteCredential(id),
  },
}));

const sourceA: Source = {
  id: 5,
  name: "ACME Careers",
  adapter_key: "greenhouse",
  base_url: "https://boards.greenhouse.io/acme",
  default_config: {},
  enabled: true,
  auto_apply_enabled: false,
  created_at: "2026-06-28T00:00:00Z",
};

const sourceB: Source = { ...sourceA, id: 6, name: "Beta Board" };

const linkedInSource: Source = {
  ...sourceA,
  id: 7,
  name: "LinkedIn Jobs",
  adapter_key: "linkedin",
  base_url: "https://www.linkedin.com/jobs/search",
};

const credentialFixture: SiteCredential = {
  id: 30,
  source_id: sourceA.id,
  name: "My session",
  enabled: true,
  created_at: "2026-06-28T00:00:00Z",
  has_cookies: true,
  has_headers: false,
  has_session: false,
};

function renderPage(ui: ReactElement = <CredentialsPage />) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("CredentialsPage", () => {
  beforeEach(() => {
    listCredentials.mockReset();
    listCredentials.mockResolvedValue([]);
    listSources.mockReset();
    listSources.mockResolvedValue([]);
    createCredential.mockReset();
    createCredential.mockResolvedValue(credentialFixture);
    updateCredential.mockReset();
    updateCredential.mockResolvedValue(credentialFixture);
    deleteCredential.mockReset();
    deleteCredential.mockResolvedValue(undefined);
  });

  it("renders the heading and prompts to create a source when none exist", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Site credentials" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("Create a source first, then add credentials for it."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an empty state when there are no stored credentials", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("No credentials stored.")).toBeInTheDocument());
  });

  it("shows the add form once a source exists", async () => {
    listSources.mockResolvedValue([sourceA, sourceB]);
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: "ACME Careers" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Beta Board" })).toBeInTheDocument();
  });

  it("creates a credential with the selected source and entered JSON", async () => {
    listSources.mockResolvedValue([sourceA, sourceB]);
    const { container } = renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByRole("combobox"), { target: { value: String(sourceB.id) } });
    fireEvent.change(screen.getByPlaceholderText("My logged-in session"), {
      target: { value: "Prod cookies" },
    });

    const [cookies, headers, session] = container.querySelectorAll("textarea");
    fireEvent.change(cookies, { target: { value: '{"sessionid": "abc"}' } });
    fireEvent.change(headers, { target: { value: '{"Authorization": "Bearer x"}' } });
    fireEvent.change(session, { target: { value: "" } });

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    await waitFor(() =>
      expect(createCredential).toHaveBeenCalledWith(
        expect.objectContaining({
          source_id: sourceB.id,
          name: "Prod cookies",
          enabled: true,
          cookies: { sessionid: "abc" },
          headers: { Authorization: "Bearer x" },
          session: {},
        }),
      ),
    );
  });

  it("defaults to the first source when the select is untouched", async () => {
    listSources.mockResolvedValue([sourceA, sourceB]);
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    await waitFor(() =>
      expect(createCredential).toHaveBeenCalledWith(
        expect.objectContaining({ source_id: sourceA.id }),
      ),
    );
  });

  it("confirms ToS risk before saving LinkedIn credentials", async () => {
    listSources.mockResolvedValue([linkedInSource]);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );
    expect(screen.getByText(/LinkedIn and Indeed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    await waitFor(() =>
      expect(createCredential).toHaveBeenCalledWith(
        expect.objectContaining({ source_id: linkedInSource.id }),
      ),
    );
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/Terms of Service/i));
    confirmSpy.mockRestore();
  });

  it("does not save LinkedIn credentials when the risk dialog is cancelled", async () => {
    listSources.mockResolvedValue([linkedInSource]);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    await waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    expect(createCredential).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("disables the save button and surfaces an error when JSON is invalid", async () => {
    listSources.mockResolvedValue([sourceA]);
    const { container } = renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    const [cookies] = container.querySelectorAll("textarea");
    fireEvent.change(cookies, { target: { value: "{not json" } });

    expect(screen.getByRole("button", { name: "Save credential" })).toBeDisabled();
    expect(screen.getByText(/Invalid JSON:/)).toBeInTheDocument();
  });

  it("errors when the form renders but no source resolves to an id", async () => {
    // A source without an id keeps the list non-empty (so the form renders) yet
    // leaves effectiveSource null, exercising the "Create a source first." guard.
    const sourceWithoutId = { ...sourceA, id: undefined } as unknown as Source;
    listSources.mockResolvedValue([sourceWithoutId]);
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    expect(await screen.findByText("Create a source first.")).toBeInTheDocument();
    expect(createCredential).not.toHaveBeenCalled();
  });

  it("shows an error banner when creating a credential fails", async () => {
    listSources.mockResolvedValue([sourceA]);
    createCredential.mockRejectedValue(new Error("Server rejected the credential."));
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save credential" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save credential" }));

    expect(await screen.findByText("Server rejected the credential.")).toBeInTheDocument();
  });

  it("lists stored credentials with their contents and source name", async () => {
    listSources.mockResolvedValue([sourceA]);
    listCredentials.mockResolvedValue([credentialFixture]);
    renderPage();

    await waitFor(() => expect(screen.getByText("My session")).toBeInTheDocument());
    const row = screen.getByText("My session").closest("tr") as HTMLElement;
    expect(within(row).getByText("ACME Careers")).toBeInTheDocument();
    expect(within(row).getByText("cookies")).toBeInTheDocument();
  });

  it("renders headers and session content chips when present", async () => {
    listSources.mockResolvedValue([sourceA]);
    listCredentials.mockResolvedValue([
      { ...credentialFixture, has_cookies: true, has_headers: true, has_session: true },
    ]);
    renderPage();

    await waitFor(() => expect(screen.getByText("My session")).toBeInTheDocument());
    const row = screen.getByText("My session").closest("tr") as HTMLElement;
    expect(within(row).getByText("cookies")).toBeInTheDocument();
    expect(within(row).getByText("headers")).toBeInTheDocument();
    expect(within(row).getByText("session")).toBeInTheDocument();
  });

  it("renders (unnamed), empty contents, and a fallback source label", async () => {
    listSources.mockResolvedValue([sourceA]);
    listCredentials.mockResolvedValue([
      {
        ...credentialFixture,
        id: 31,
        source_id: 999,
        name: "",
        enabled: false,
        has_cookies: false,
        has_headers: false,
        has_session: false,
      },
    ]);
    renderPage();

    await waitFor(() => expect(screen.getByText("(unnamed)")).toBeInTheDocument());
    expect(screen.getByText("empty")).toBeInTheDocument();
    expect(screen.getByText("Source 999")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable" })).toBeInTheDocument();
  });

  it("toggles a credential's enabled state", async () => {
    listSources.mockResolvedValue([sourceA]);
    listCredentials.mockResolvedValue([credentialFixture]);
    renderPage();

    await waitFor(() => expect(screen.getByText("My session")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Disable" }));

    await waitFor(() =>
      expect(updateCredential).toHaveBeenCalledWith(credentialFixture.id, { enabled: false }),
    );
  });

  it("deletes a credential", async () => {
    listSources.mockResolvedValue([sourceA]);
    listCredentials.mockResolvedValue([credentialFixture]);
    renderPage();

    await waitFor(() => expect(screen.getByText("My session")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteCredential).toHaveBeenCalledWith(credentialFixture.id));
  });
});
