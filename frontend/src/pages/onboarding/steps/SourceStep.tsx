import type { FormEvent } from "react";
import { Button, Card, Field } from "../../../components/ui";

interface SourceStepProps {
  busy: boolean;
  detectUrl: string;
  sourceName: string;
  baseUrl: string;
  effectiveAdapter: string;
  adapters: string[];
  onDetectUrlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onBaseUrlChange: (value: string) => void;
  onAdapterChange: (value: string) => void;
  onDetect: (e: FormEvent) => void;
  onSubmit: (e: FormEvent) => void;
  onBack: () => void;
}

export function SourceStep({
  busy,
  detectUrl,
  sourceName,
  baseUrl,
  effectiveAdapter,
  adapters,
  onDetectUrlChange,
  onSourceNameChange,
  onBaseUrlChange,
  onAdapterChange,
  onDetect,
  onSubmit,
  onBack,
}: SourceStepProps) {
  return (
    <Card title="Add a job board">
      <p className="onboarding-lead">
        Paste a careers or search URL and we will try to detect the board automatically.
      </p>
      <form onSubmit={onDetect} className="onboarding-detect">
        <Field label="Careers or search URL">
          <input
            value={detectUrl}
            onChange={(e) => onDetectUrlChange(e.target.value)}
            placeholder="https://boards.greenhouse.io/acme"
          />
        </Field>
        <Button type="submit" variant="ghost" disabled={busy || !detectUrl.trim()}>
          Detect board
        </Button>
      </form>

      <form onSubmit={onSubmit}>
        <div className="form-grid">
          <Field label="Display name">
            <input
              value={sourceName}
              onChange={(e) => onSourceNameChange(e.target.value)}
              placeholder="ACME Careers"
              required
            />
          </Field>
          <Field label="Scraper">
            <select value={effectiveAdapter} onChange={(e) => onAdapterChange(e.target.value)}>
              {adapters.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Base URL">
            <input
              value={baseUrl}
              onChange={(e) => onBaseUrlChange(e.target.value)}
              placeholder="https://boards.greenhouse.io/acme"
              required
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
