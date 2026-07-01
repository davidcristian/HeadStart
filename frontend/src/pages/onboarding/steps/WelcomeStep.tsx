import { Button, Card } from "../../../components/ui";

interface WelcomeStepProps {
  busy: boolean;
  onStart: () => void;
  onSkip: () => void;
}

export function WelcomeStep({ busy, onStart, onSkip }: WelcomeStepProps) {
  return (
    <Card title="Welcome to HeadStart">
      <p className="onboarding-lead">
        In a few steps you will connect a job board, pick where alerts go, and run your first
        search.
      </p>
      <ul className="onboarding-checklist">
        <li>Add a job board source (Greenhouse, Lever, Indeed, …)</li>
        <li>Choose a notification channel (ntfy, email, Slack, …)</li>
        <li>Create a search and run it once to confirm everything works</li>
      </ul>
      <div className="onboarding-actions">
        <Button onClick={onStart}>Get started</Button>
        <Button variant="ghost" onClick={onSkip} disabled={busy}>
          Skip for now
        </Button>
      </div>
    </Card>
  );
}
