import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { sampleJob } from "../test/fixtures";
import { JobList } from "./JobList";
import type { Job } from "../types";

function setMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function makeJob(overrides: Partial<Job> = {}): Job {
  return { ...sampleJob, ...overrides };
}

afterEach(() => {
  setMatchMedia(false);
});

describe("JobList (desktop table)", () => {
  it("renders a job row with a linked title and every action", () => {
    setMatchMedia(false);
    const onStatusChange = vi.fn();
    const onApply = vi.fn();
    render(
      <JobList
        jobs={[makeJob()]}
        onStatusChange={onStatusChange}
        canApply={() => true}
        onApply={onApply}
      />,
    );

    const link = screen.getByRole("link", { name: "Software Engineer" });
    expect(link).toHaveAttribute("href", sampleJob.url);
    expect(screen.getByText(sampleJob.summary)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith(sampleJob);

    fireEvent.click(screen.getByRole("button", { name: "Seen" }));
    fireEvent.click(screen.getByRole("button", { name: "Applied" }));
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(onStatusChange).toHaveBeenCalledWith(sampleJob.id, "seen");
    expect(onStatusChange).toHaveBeenCalledWith(sampleJob.id, "applied");
    expect(onStatusChange).toHaveBeenCalledWith(sampleJob.id, "archived");
  });

  it("falls back to placeholders and omits the summary and apply button", () => {
    setMatchMedia(false);
    render(
      <JobList
        jobs={[
          makeJob({
            company: "",
            location: "",
            salary: "",
            summary: "",
            url: "",
          }),
        ]}
        onStatusChange={vi.fn()}
      />,
    );

    // Title is plain text (no link) when url is empty.
    expect(screen.queryByRole("link", { name: "Software Engineer" })).not.toBeInTheDocument();
    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });

  it("renders a plain title when the job url is a javascript: scheme", () => {
    setMatchMedia(false);
    render(
      <JobList
        jobs={[makeJob({ url: "javascript:alert(1)" })]}
        onStatusChange={vi.fn()}
      />,
    );

    expect(screen.queryByRole("link", { name: "Software Engineer" })).not.toBeInTheDocument();
    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
  });

  it("hides Seen for seen/closed jobs and Applied for applied jobs", () => {
    setMatchMedia(false);
    render(
      <JobList
        jobs={[makeJob({ status: "seen" }), makeJob({ id: 2, status: "applied" })]}
        onStatusChange={vi.fn()}
      />,
    );

    // Seen row: no "Seen" button; applied row: no "Applied" button.
    const seenButtons = screen.queryAllByRole("button", { name: "Seen" });
    const appliedButtons = screen.queryAllByRole("button", { name: "Applied" });
    expect(seenButtons).toHaveLength(1); // only from the applied row
    expect(appliedButtons).toHaveLength(1); // only from the seen row
  });

  it("hides Seen for closed jobs", () => {
    setMatchMedia(false);
    render(<JobList jobs={[makeJob({ status: "closed" })]} onStatusChange={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Seen" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
  });

  it("does not render an apply button when canApply is omitted", () => {
    setMatchMedia(false);
    render(<JobList jobs={[makeJob()]} onStatusChange={vi.fn()} onApply={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });
});

describe("JobList (mobile cards)", () => {
  it("renders cards with metadata and apply", () => {
    setMatchMedia(true);
    const onApply = vi.fn();
    render(
      <JobList
        jobs={[makeJob()]}
        onStatusChange={vi.fn()}
        canApply={() => true}
        onApply={onApply}
      />,
    );

    const card = document.querySelector(".job-card") as HTMLElement;
    expect(card).not.toBeNull();
    expect(within(card).getByText(/ACME · Remote/)).toBeInTheDocument();
    expect(within(card).getByText(sampleJob.salary)).toBeInTheDocument();
    expect(within(card).getByText(sampleJob.summary)).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith(sampleJob);
  });

  it("shows an unknown-company fallback when company and location are empty", () => {
    setMatchMedia(true);
    render(
      <JobList
        jobs={[makeJob({ company: "", location: "", salary: "", summary: "" })]}
        onStatusChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Unknown company")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });
});
