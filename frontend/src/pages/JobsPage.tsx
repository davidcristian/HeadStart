/** Feed of jobs discovered so far, filterable by search and triage status. */

import { useCallback, useMemo, useState } from "react";
import { ApplyJobDialog } from "../components/ApplyJobDialog";
import { JobList } from "../components/JobList";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
import {
  useFeedUrl,
  useJobs,
  useMeta,
  useProfile,
  useSearches,
  useSources,
} from "../hooks/queries";
import { useRotateFeedUrl, useUpdateJob } from "../hooks/mutations";
import { usePullToRefresh } from "../hooks/usePullToRefresh";
import { canAutoApply } from "../lib/canAutoApply";
import { renderCoverLetterTemplate } from "../lib/coverLetter";
import { planLabel } from "../lib/plan";
import type { Job, JobStatus } from "../types";

const STATUS_FILTERS: Array<{ value: "" | JobStatus; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "seen", label: "Seen" },
  { value: "applied", label: "Applied" },
  { value: "archived", label: "Archived" },
  { value: "closed", label: "Closed" },
];

function buildFeedUrl(baseUrl: string, searchId: number | "", status: "" | JobStatus): string {
  const url = new URL(baseUrl);
  if (searchId !== "") {
    url.searchParams.set("search_id", String(searchId));
  }
  if (status !== "") {
    url.searchParams.set("status", status);
  }
  return url.toString();
}

export function JobsPage() {
  const [searchId, setSearchId] = useState<number | "">("");
  const [status, setStatus] = useState<"" | JobStatus>("");
  const [feedMessage, setFeedMessage] = useState<string | null>(null);
  const [applyJob, setApplyJob] = useState<Job | null>(null);
  const searches = useSearches();
  const sources = useSources();
  const profile = useProfile();
  const meta = useMeta();
  const rssAllowed = meta.data?.plan.features.rss_feed ?? false;
  const jobs = useJobs(
    searchId === "" ? undefined : Number(searchId),
    status === "" ? undefined : status,
  );
  const feed = useFeedUrl(rssAllowed);
  const updateJob = useUpdateJob();
  const rotateFeed = useRotateFeedUrl();

  const { refetch } = jobs;
  const refreshJobs = useCallback(() => {
    void refetch();
  }, [refetch]);

  const { pulling, refreshing } = usePullToRefresh(refreshJobs);

  async function setJobStatus(jobId: number, next: "seen" | "applied" | "archived") {
    await updateJob.mutateAsync({ id: jobId, status: next });
  }

  async function copyFeedUrl() {
    if (!feed.data) return;
    const url = buildFeedUrl(feed.data.url, searchId, status);
    await navigator.clipboard.writeText(url);
    setFeedMessage("RSS feed URL copied to clipboard.");
  }

  async function rotateFeedUrl() {
    await rotateFeed.mutateAsync();
    setFeedMessage("RSS feed link regenerated. Update any feed readers using the old URL.");
  }

  const filteredFeedUrl = feed.data ? buildFeedUrl(feed.data.url, searchId, status) : "";

  const appliers = useMemo(() => meta.data?.appliers ?? [], [meta.data?.appliers]);
  const jobCanApply = useCallback(
    (job: Job) => canAutoApply(job, searches.data ?? [], sources.data ?? [], appliers),
    [searches.data, sources.data, appliers],
  );

  const applyCoverLetter = useMemo(() => {
    if (!applyJob) return "";
    const template = profile.data?.cover_letter_template ?? "";
    if (!template.trim()) return "";
    return renderCoverLetterTemplate(template, applyJob.company, applyJob.title);
  }, [applyJob, profile.data?.cover_letter_template]);

  const applyAutoApplyEnabled = useMemo(() => {
    if (!applyJob) return false;
    const search = searches.data?.find((item) => item.id === applyJob.search_id);
    const source = sources.data?.find((item) => item.id === search?.source_id);
    return source?.auto_apply_enabled ?? false;
  }, [applyJob, searches.data, sources.data]);

  return (
    <div className="jobs-page">
      {(pulling || refreshing) && (
        <div className="pull-refresh" aria-live="polite">
          {refreshing ? "Refreshing jobs..." : "Release to refresh"}
        </div>
      )}
      <h1>Jobs</h1>
      <Card title="RSS feed" className="rss-card">
        {!rssAllowed && meta.data && (
          <>
            <p className="muted">
              RSS export is available on the Pro plan. You are on the{" "}
              {planLabel(meta.data.plan.plan)} plan.
            </p>
            <p>
              <a href="/pricing">Compare plans</a>
            </p>
          </>
        )}
        {rssAllowed && feed.isPending && <p>Loading feed URL...</p>}
        {rssAllowed && feed.isError && <Banner kind="error">Could not load RSS feed URL.</Banner>}
        {rssAllowed && feed.data && (
          <>
            <p className="muted">
              Subscribe in any RSS reader. The URL respects the search and status filters selected
              below.
            </p>
            <Field label="Feed URL" hint="Anyone with this link can read your job feed.">
              <input readOnly value={filteredFeedUrl} onFocus={(e) => e.target.select()} />
            </Field>
            <div className="row-actions">
              <Button onClick={copyFeedUrl}>Copy feed URL</Button>
              <Button variant="ghost" onClick={rotateFeedUrl}>
                Regenerate link
              </Button>
            </div>
            {feedMessage && <p className="muted">{feedMessage}</p>}
          </>
        )}
      </Card>
      <Card
        title="Discovered jobs"
        actions={
          <div className="card-actions job-filters">
            <Field label="">
              <select value={status} onChange={(e) => setStatus(e.target.value as "" | JobStatus)}>
                {STATUS_FILTERS.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="">
              <select
                value={searchId}
                onChange={(e) => setSearchId(e.target.value === "" ? "" : Number(e.target.value))}
              >
                <option value="">All searches</option>
                {searches.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        }
      >
        {jobs.isPending && <p>Loading...</p>}
        {jobs.data && jobs.data.length === 0 && (
          <EmptyState>No jobs seen yet. They appear here as searches run.</EmptyState>
        )}
        {jobs.data && jobs.data.length > 0 && (
          <JobList
            jobs={jobs.data}
            onStatusChange={setJobStatus}
            canApply={jobCanApply}
            onApply={setApplyJob}
          />
        )}
      </Card>
      {applyJob && (
        <ApplyJobDialog
          job={applyJob}
          open
          initialCoverLetter={applyCoverLetter}
          profileReady={profile.data?.exists ?? false}
          autoApplyEnabled={applyAutoApplyEnabled}
          onClose={() => setApplyJob(null)}
        />
      )}
    </div>
  );
}
