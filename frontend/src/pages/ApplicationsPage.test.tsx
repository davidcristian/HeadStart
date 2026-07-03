import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { sampleApplicationPipelineItem } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { ApplicationsPage } from "./ApplicationsPage";

function renderApplicationsPage() {
  return renderWithClient(
    <MemoryRouter>
      <ApplicationsPage />
    </MemoryRouter>,
  );
}

describe("ApplicationsPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    renderApplicationsPage();

    expect(screen.getByRole("heading", { name: "Applications" })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/No applications in the pipeline yet/i)).toBeInTheDocument(),
    );
  });

  it("lists pipeline items", async () => {
    mockApi.listApplications.mockResolvedValue([sampleApplicationPipelineItem]);
    renderApplicationsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(
      screen.getByText("Awaiting reply", { selector: ".badge-pipeline-awaiting_reply" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ACME")).toBeInTheDocument();
  });

  it("filters by pipeline stage", async () => {
    mockApi.listApplications.mockResolvedValue([sampleApplicationPipelineItem]);
    renderApplicationsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(mockApi.listApplications).toHaveBeenCalledWith(undefined);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "apply_failed" },
    });

    await waitFor(() => expect(mockApi.listApplications).toHaveBeenCalledWith("apply_failed"));
  });

  it("expands the attempt timeline", async () => {
    mockApi.listApplications.mockResolvedValue([sampleApplicationPipelineItem]);
    renderApplicationsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Timeline" }));

    const timeline = await screen.findByRole("list");
    expect(timeline).toHaveTextContent("Submitted");
    expect(timeline).toHaveTextContent("ID: gh-123");
  });
});
