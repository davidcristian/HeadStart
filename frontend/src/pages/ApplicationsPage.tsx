/** Application pipeline: track apply outcomes and recruiter follow-up readiness. */

import { useState } from "react";
import { ApplicationPipelineList } from "../components/ApplicationPipelineList";
import { Card, EmptyState, Field } from "../components/ui";
import { useApplications } from "../hooks/queries";
import type { ApplicationPipelineStage } from "../types";

const STAGE_FILTERS: Array<{ value: "" | ApplicationPipelineStage; label: string }> = [
  { value: "", label: "All stages" },
  { value: "queued", label: "Submitting" },
  { value: "awaiting_reply", label: "Awaiting reply" },
  { value: "ghosted", label: "Ghosted" },
  { value: "interview_pending", label: "Interview pending" },
  { value: "rejected", label: "Rejected" },
  { value: "apply_failed", label: "Apply failed" },
  { value: "closed", label: "Listing closed" },
  { value: "archived", label: "Archived" },
];

export function ApplicationsPage() {
  const [stage, setStage] = useState<"" | ApplicationPipelineStage>("");
  const applications = useApplications(stage === "" ? undefined : stage);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Applications</h1>
        <p className="muted page-lead">
          Track jobs you applied to through HeadStart. Ghosted applications had no recruiter reply
          within the configured silence window.
        </p>
      </header>

      <Card>
        <div className="toolbar">
          <Field label="Pipeline stage">
            <select
              value={stage}
              onChange={(event) => setStage(event.target.value as "" | ApplicationPipelineStage)}
            >
              {STAGE_FILTERS.map((filter) => (
                <option key={filter.value || "all"} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {applications.isPending && <p>Loading...</p>}
        {applications.isError && (
          <p className="status-bad">Could not load applications. Try again shortly.</p>
        )}
        {applications.data && applications.data.length === 0 && (
          <EmptyState>
            No applications in the pipeline yet. Apply from the Jobs page or enable auto-apply on a
            source.
          </EmptyState>
        )}
        {applications.data && applications.data.length > 0 && (
          <ApplicationPipelineList items={applications.data} />
        )}
      </Card>
    </div>
  );
}
