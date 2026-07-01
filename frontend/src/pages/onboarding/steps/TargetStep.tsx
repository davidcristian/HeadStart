import type { FormEvent } from "react";
import { Button, Card, Field } from "../../../components/ui";
import type { Json } from "../../../types";
import { NotifierFields } from "../NotifierFields";

interface TargetStepProps {
  busy: boolean;
  targetName: string;
  effectiveNotifier: string;
  notifiers: string[];
  notifierConfig: Json;
  onTargetNameChange: (value: string) => void;
  onNotifierTypeChange: (value: string) => void;
  onNotifierConfigChange: (config: Json) => void;
  onSubmit: (e: FormEvent) => void;
  onBack: () => void;
}

export function TargetStep({
  busy,
  targetName,
  effectiveNotifier,
  notifiers,
  notifierConfig,
  onTargetNameChange,
  onNotifierTypeChange,
  onNotifierConfigChange,
  onSubmit,
  onBack,
}: TargetStepProps) {
  return (
    <Card title="Where should alerts go?">
      <p className="onboarding-lead">
        Pick a channel. You can add more targets later from Notifications.
      </p>
      <form onSubmit={onSubmit}>
        <div className="form-grid">
          <Field label="Name">
            <input
              value={targetName}
              onChange={(e) => onTargetNameChange(e.target.value)}
              placeholder="My phone"
              required
            />
          </Field>
          <Field label="Channel">
            <select
              value={effectiveNotifier}
              onChange={(e) => onNotifierTypeChange(e.target.value)}
            >
              {notifiers.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </Field>
          <NotifierFields
            notifierType={effectiveNotifier}
            config={notifierConfig}
            onChange={onNotifierConfigChange}
          />
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
