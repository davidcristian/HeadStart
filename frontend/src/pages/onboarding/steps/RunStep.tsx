import { Button, Card } from "../../../components/ui";

interface RunStepProps {
  busy: boolean;
  searchId: number | null;
  onRun: () => void;
  onComplete: () => void;
}

export function RunStep({ busy, searchId, onRun, onComplete }: RunStepProps) {
  return (
    <Card title="Run your first check">
      <p className="onboarding-lead">
        We will scrape the board now and send any new matches to your notification channel.
      </p>
      <div className="onboarding-actions">
        <Button onClick={onRun} disabled={busy || searchId == null}>
          {busy ? "Running..." : "Run now"}
        </Button>
        <Button onClick={onComplete} disabled={busy}>
          Go to Jobs
        </Button>
      </div>
      <p className="onboarding-footnote">
        Your search will keep polling every 15 minutes. Adjust interval and filters on the Searches
        page any time.
      </p>
    </Card>
  );
}
