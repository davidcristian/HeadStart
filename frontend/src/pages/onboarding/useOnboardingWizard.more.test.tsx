import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FormEvent } from "react";
import type { User } from "../../types";
import { mockApi, resetMockApi } from "../../test/mockApi";
import { useOnboardingWizard } from "./useOnboardingWizard";

const navigate = vi.fn();
const refreshUser = vi.fn(async () => undefined);

const user: User = {
  id: 1,
  email: "new@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: null,
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ user, refreshUser }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

const fakeEvent = { preventDefault: vi.fn() } as unknown as FormEvent;

async function renderWizard() {
  const hook = renderHook(() => useOnboardingWizard(), { wrapper });
  // Wait for meta to load so the notifier-init effect settles.
  await waitFor(() => expect(hook.result.current.notifiers.length).toBeGreaterThan(0));
  return hook;
}

describe("useOnboardingWizard", () => {
  beforeEach(() => {
    resetMockApi();
    navigate.mockClear();
    refreshUser.mockClear();
  });

  it("surfaces skipSetup errors", async () => {
    mockApi.completeOnboarding.mockRejectedValueOnce(new Error("save failed"));
    const { result } = await renderWizard();
    await act(async () => {
      await result.current.skipSetup();
    });
    expect(result.current.error).toBe("save failed");
  });

  it("surfaces completeSetup errors", async () => {
    mockApi.completeOnboarding.mockRejectedValueOnce(new Error("complete failed"));
    const { result } = await renderWizard();
    await act(async () => {
      await result.current.completeSetup();
    });
    expect(result.current.error).toBe("complete failed");
  });

  it("changes notifier type and resets config to defaults", async () => {
    const { result } = await renderWizard();
    act(() => result.current.onNotifierTypeChange("telegram"));
    expect(result.current.notifierConfig).toEqual({ bot_token: "", chat_id: "" });

    act(() => result.current.onNotifierTypeChange("unknown-channel"));
    expect(result.current.notifierConfig).toEqual({});
  });

  it("initializes an unknown first notifier with an empty config", async () => {
    mockApi.meta.mockResolvedValue({
      ...(await mockApi.meta()),
      notifiers: ["custom-channel"],
    });
    const { result } = await renderWizard();
    await waitFor(() => expect(result.current.effectiveNotifier).toBe("custom-channel"));
    expect(result.current.notifierConfig).toEqual({});
  });

  it("populates fields from a successful detect", async () => {
    const { result } = await renderWizard();
    act(() => result.current.setDetectUrl("  https://boards.greenhouse.io/acme  "));
    await act(async () => {
      await result.current.detectFromUrl(fakeEvent);
    });
    expect(mockApi.detectSource).toHaveBeenCalledWith("https://boards.greenhouse.io/acme");
    expect(result.current.sourceName).toBe("ACME Careers");
    expect(result.current.adapterKey).toBe("greenhouse");
    expect(result.current.baseUrl).toBe("https://boards.greenhouse.io/acme");
    expect(result.current.queryUrl).toBe("https://boards.greenhouse.io/acme");
    expect(result.current.searchName).toBe("ACME Careers");
    expect(result.current.notice).toContain("Detected greenhouse board for ACME Careers.");
  });

  it("guards the source step when name and base url are blank", async () => {
    const { result } = await renderWizard();
    act(() => {
      result.current.setSourceName("   ");
      result.current.setBaseUrl("");
    });
    await act(async () => {
      await result.current.createSourceStep(fakeEvent);
    });
    expect(result.current.error).toBe("Name and base URL are required.");
    expect(result.current.step).toBe("welcome");
  });

  it("surfaces createTarget errors", async () => {
    mockApi.createSource.mockResolvedValueOnce({
      id: 5,
      name: "ACME",
      adapter_key: "greenhouse",
      base_url: "https://x.test",
      default_config: {},
      enabled: true,
      auto_apply_enabled: false,
      created_at: "2026-06-28T00:00:00Z",
    });
    mockApi.createTarget.mockRejectedValueOnce(new Error("target boom"));
    const { result } = await renderWizard();
    act(() => {
      result.current.setSourceName("ACME");
      result.current.setBaseUrl("https://x.test");
    });
    await act(async () => {
      await result.current.createSourceStep(fakeEvent);
    });
    await act(async () => {
      await result.current.createTargetStep(fakeEvent);
    });
    expect(result.current.error).toBe("target boom");
    expect(result.current.step).toBe("target");
  });

  it("surfaces createSearch errors and passes trimmed keywords", async () => {
    mockApi.createSource.mockResolvedValueOnce({
      id: 5,
      name: "ACME",
      adapter_key: "greenhouse",
      base_url: "https://x.test",
      default_config: {},
      enabled: true,
      auto_apply_enabled: false,
      created_at: "2026-06-28T00:00:00Z",
    });
    mockApi.createTarget.mockResolvedValueOnce({
      id: 7,
      name: "My alerts",
      type: "ntfy",
      config: {},
      created_at: "2026-06-28T00:00:00Z",
    });
    mockApi.createSearch.mockRejectedValueOnce(new Error("search boom"));
    const { result } = await renderWizard();
    act(() => {
      result.current.setSourceName("ACME");
      result.current.setBaseUrl("https://x.test");
    });
    await act(async () => {
      await result.current.createSourceStep(fakeEvent);
    });
    await act(async () => {
      await result.current.createTargetStep(fakeEvent);
    });
    act(() => result.current.setKeywords("  remote python  "));
    await act(async () => {
      await result.current.createSearchStep(fakeEvent);
    });
    expect(mockApi.createSearch).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { keywords: "remote python" } }),
    );
    expect(result.current.error).toBe("search boom");
    expect(result.current.step).toBe("search");
  });

  it("skips setup and navigates to searches", async () => {
    const { result } = await renderWizard();
    await act(async () => {
      await result.current.skipSetup();
    });
    expect(mockApi.completeOnboarding).toHaveBeenCalled();
    expect(refreshUser).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith("/app/searches", { replace: true });
    expect(result.current.error).toBeUndefined();
  });

  it("completes setup and navigates to jobs", async () => {
    const { result } = await renderWizard();
    await act(async () => {
      await result.current.completeSetup();
    });
    expect(mockApi.completeOnboarding).toHaveBeenCalled();
    expect(refreshUser).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith("/app/jobs", { replace: true });
    expect(result.current.error).toBeUndefined();
  });
});
