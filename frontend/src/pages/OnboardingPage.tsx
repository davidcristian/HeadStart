/** First-run wizard: source → notifications → search → run. */

import { Navigate } from "react-router-dom";
import { Brand } from "../components/Brand";
import { Banner } from "../components/ui";
import { STEPS } from "./onboarding/constants";
import { RunStep } from "./onboarding/steps/RunStep";
import { SearchStep } from "./onboarding/steps/SearchStep";
import { SourceStep } from "./onboarding/steps/SourceStep";
import { TargetStep } from "./onboarding/steps/TargetStep";
import { WelcomeStep } from "./onboarding/steps/WelcomeStep";
import { useOnboardingWizard } from "./onboarding/useOnboardingWizard";

export function OnboardingPage() {
  const wizard = useOnboardingWizard();

  if (wizard.user?.onboarding_completed_at) {
    return <Navigate to="/app/searches" replace />;
  }

  return (
    <div className="onboarding-screen">
      <div className="onboarding-shell">
        <Brand to="/app/onboarding" />

        <ol className="onboarding-steps" aria-label="Setup progress">
          {STEPS.map((item, index) => (
            <li
              key={item.key}
              className={
                index < wizard.stepIndex
                  ? "done"
                  : index === wizard.stepIndex
                    ? "current"
                    : undefined
              }
            >
              <span className="onboarding-step-num">{index + 1}</span>
              <span className="onboarding-step-label">{item.label}</span>
            </li>
          ))}
        </ol>

        {wizard.error && <Banner kind="error">{wizard.error}</Banner>}
        {wizard.notice && <Banner kind="info">{wizard.notice}</Banner>}

        {wizard.step === "welcome" && (
          <WelcomeStep
            busy={wizard.busy}
            onStart={() => wizard.setStep("source")}
            onSkip={() => void wizard.skipSetup()}
          />
        )}

        {wizard.step === "source" && (
          <SourceStep
            busy={wizard.busy}
            detectUrl={wizard.detectUrl}
            sourceName={wizard.sourceName}
            baseUrl={wizard.baseUrl}
            effectiveAdapter={wizard.effectiveAdapter}
            adapters={wizard.adapters}
            onDetectUrlChange={wizard.setDetectUrl}
            onSourceNameChange={wizard.setSourceName}
            onBaseUrlChange={wizard.setBaseUrl}
            onAdapterChange={wizard.setAdapterKey}
            onDetect={(e) => void wizard.detectFromUrl(e)}
            onSubmit={(e) => void wizard.createSourceStep(e)}
            onBack={() => wizard.setStep("welcome")}
          />
        )}

        {wizard.step === "target" && (
          <TargetStep
            busy={wizard.busy}
            targetName={wizard.targetName}
            effectiveNotifier={wizard.effectiveNotifier}
            notifiers={wizard.notifiers}
            notifierConfig={wizard.notifierConfig}
            onTargetNameChange={wizard.setTargetName}
            onNotifierTypeChange={wizard.onNotifierTypeChange}
            onNotifierConfigChange={wizard.setNotifierConfig}
            onSubmit={(e) => void wizard.createTargetStep(e)}
            onBack={() => wizard.setStep("source")}
          />
        )}

        {wizard.step === "search" && (
          <SearchStep
            busy={wizard.busy}
            searchName={wizard.searchName}
            queryUrl={wizard.queryUrl}
            keywords={wizard.keywords}
            onSearchNameChange={wizard.setSearchName}
            onQueryUrlChange={wizard.setQueryUrl}
            onKeywordsChange={wizard.setKeywords}
            onSubmit={(e) => void wizard.createSearchStep(e)}
            onBack={() => wizard.setStep("target")}
          />
        )}

        {wizard.step === "run" && (
          <RunStep
            busy={wizard.busy}
            searchId={wizard.searchId}
            onRun={() => void wizard.runFirstSearch()}
            onComplete={() => void wizard.completeSetup()}
          />
        )}
      </div>
    </div>
  );
}
