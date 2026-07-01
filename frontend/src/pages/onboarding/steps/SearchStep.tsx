import type { FormEvent } from "react";
import { Button, Card, Field } from "../../../components/ui";

interface SearchStepProps {
  busy: boolean;
  searchName: string;
  queryUrl: string;
  keywords: string;
  onSearchNameChange: (value: string) => void;
  onQueryUrlChange: (value: string) => void;
  onKeywordsChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onBack: () => void;
}

export function SearchStep({
  busy,
  searchName,
  queryUrl,
  keywords,
  onSearchNameChange,
  onQueryUrlChange,
  onKeywordsChange,
  onSubmit,
  onBack,
}: SearchStepProps) {
  return (
    <Card title="Create your first search">
      <p className="onboarding-lead">
        This is the query HeadStart will poll on a schedule. You can refine filters later.
      </p>
      <form onSubmit={onSubmit}>
        <div className="form-grid">
          <Field label="Search name">
            <input
              value={searchName}
              onChange={(e) => onSearchNameChange(e.target.value)}
              placeholder="Backend engineer roles"
              required
            />
          </Field>
          <Field label="Query URL">
            <input
              value={queryUrl}
              onChange={(e) => onQueryUrlChange(e.target.value)}
              placeholder="https://boards.greenhouse.io/acme"
              required
            />
          </Field>
          <Field
            label="Keywords (optional)"
            hint="Only notify when title/company/location matches."
          >
            <input
              value={keywords}
              onChange={(e) => onKeywordsChange(e.target.value)}
              placeholder="engineer backend"
            />
          </Field>
        </div>
        <div className="onboarding-actions">
          <Button type="button" variant="ghost" onClick={onBack}>
            Back
          </Button>
          <Button type="submit" disabled={busy}>
            Continue
          </Button>
        </div>
      </form>
    </Card>
  );
}
