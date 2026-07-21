import { mockApi } from "../../test/mockApi";
import { act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithClient } from "../../test/renderWithClient";
import { SettingsBillingCard } from "./SettingsBillingCard";
import type { BillingStatus } from "../../types";

type BillingStatusResolved = Awaited<ReturnType<typeof mockApi.billingStatus>>;

const status: BillingStatus = {
  configured: true,
  plan: "free",
  subscription_status: null,
  has_stripe_subscription: false,
  can_checkout: true,
  can_manage: false,
  trial_days: 14,
  currency: "eur",
};

describe("SettingsBillingCard (unmount races)", () => {
  beforeEach(() => {
    mockApi.billingStatus.mockReset();
  });

  it("ignores billing status that resolves after unmount", async () => {
    let resolveStatus!: (value: BillingStatusResolved) => void;
    mockApi.billingStatus.mockReturnValue(
      new Promise<BillingStatusResolved>((resolve) => {
        resolveStatus = resolve;
      }),
    );

    const { container, unmount } = renderWithClient(<SettingsBillingCard userPlan="free" />);
    await waitFor(() => expect(mockApi.billingStatus).toHaveBeenCalled());
    unmount();
    await act(async () => {
      resolveStatus(status as BillingStatusResolved);
    });

    expect(container).toBeEmptyDOMElement();
  });

  it("ignores a billing status failure that lands after unmount", async () => {
    let rejectStatus!: (reason: Error) => void;
    mockApi.billingStatus.mockReturnValue(
      new Promise<BillingStatusResolved>((_resolve, reject) => {
        rejectStatus = reject;
      }),
    );

    const { container, unmount } = renderWithClient(<SettingsBillingCard userPlan="free" />);
    await waitFor(() => expect(mockApi.billingStatus).toHaveBeenCalled());
    unmount();
    await act(async () => {
      rejectStatus(new Error("offline"));
    });

    expect(container).toBeEmptyDOMElement();
  });
});
