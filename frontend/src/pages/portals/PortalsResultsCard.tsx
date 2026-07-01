import { Card, EmptyState } from "../../components/ui";
import type { PortalSearchResult } from "../../types";

type PortalsResultsCardProps = {
  results: PortalSearchResult;
};

export function PortalsResultsCard({ results }: PortalsResultsCardProps) {
  return (
    <Card title={`Results (${results.items.length})`}>
      <p className="muted">
        Searched {results.portals_searched} portal{results.portals_searched === 1 ? "" : "s"}
        {results.portals_failed > 0
          ? `; ${results.portals_failed} failed (see errors below)`
          : ""}
        .
      </p>
      {results.errors.length > 0 && (
        <ul className="portal-search-errors">
          {results.errors.map((item) => (
            <li key={item.portal_id}>
              <strong>{item.company_name}:</strong> {item.error}
            </li>
          ))}
        </ul>
      )}
      {results.items.length === 0 ? (
        <EmptyState>
          No matching jobs right now. Try broader keywords or more companies.
        </EmptyState>
      ) : (
        <ul className="portal-results-list">
          {results.items.map((job) => (
            <li key={`${job.portal_id}-${job.external_id}`} className="portal-result-row">
              <div>
                <strong>{job.title}</strong>
                <div className="muted">
                  {job.company_name}
                  {job.location ? ` · ${job.location}` : ""}
                </div>
              </div>
              {job.url ? (
                <a href={job.url} target="_blank" rel="noreferrer">
                  View
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
