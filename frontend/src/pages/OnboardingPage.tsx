/** First-run wizard: source → notifications → search → run. */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { Banner, Button, Card, Field } from "../components/ui";
import { useMeta } from "../hooks/queries";
import {
  useCreateSearch,
  useCreateSource,
  useCreateTarget,
  useRunSearch,
} from "../hooks/mutations";
import type { Json } from "../types";

type Step = "welcome" | "source" | "target" | "search" | "run";

const STEPS: { key: Step; label: string }[] = [
  { key: "welcome", label: "Welcome" },
  { key: "source", label: "Source" },
  { key: "target", label: "Notify" },
  { key: "search", label: "Search" },
  { key: "run", label: "Run" },
];

const NOTIFIER_DEFAULTS: Record<string, Json> = {
  ntfy: { server_url: "https://ntfy.sh", topic: "", priority: "default" },
  email: { to: "" },
  slack: { webhook_url: "" },
  discord: { webhook_url: "" },
  telegram: { bot_token: "", chat_id: "" },
  webhook: { webhook_url: "" },
};

const NOTIFIER_HINTS: Record<string, string> = {
  ntfy: "Subscribe to your topic in the ntfy app, or visit ntfy.sh/your-topic in a browser.",
  email: "Requires SMTP_* env vars on the server.",
  slack: "Paste an incoming webhook URL from your Slack workspace.",
  discord: "Paste a channel webhook URL from your Discord server.",
  telegram: "Use a bot token from @BotFather and your chat id.",
  webhook: "HTTPS endpoint that receives a JSON payload per job.",
};

export function OnboardingPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const meta = useMeta();
  const createSource = useCreateSource();
  const createTarget = useCreateTarget();
  const createSearch = useCreateSearch();
  const runSearch = useRunSearch();

  const [step, setStep] = useState<Step>("welcome");
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);

  const [sourceId, setSourceId] = useState<number | null>(null);
  const [targetId, setTargetId] = useState<number | null>(null);
  const [searchId, setSearchId] = useState<number | null>(null);

  const [detectUrl, setDetectUrl] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [adapterKey, setAdapterKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [queryUrl, setQueryUrl] = useState("");

  const [targetName, setTargetName] = useState("My alerts");
  const [notifierType, setNotifierType] = useState("");
  const [notifierConfig, setNotifierConfig] = useState<Json>({});

  const [searchName, setSearchName] = useState("");
  const [keywords, setKeywords] = useState("");

  const adapters = meta.data?.scrapers ?? [];
  const notifiers = meta.data?.notifiers ?? [];
  const effectiveAdapter = adapterKey || adapters[0] || "";
  const effectiveNotifier = notifierType || notifiers[0] || "ntfy";

  useEffect(() => {
    if (!meta.data?.notifiers.length || notifierType) return;
    const initial = meta.data.notifiers.includes("ntfy") ? "ntfy" : meta.data.notifiers[0];
    setNotifierType(initial);
    setNotifierConfig(NOTIFIER_DEFAULTS[initial] ?? {});
  }, [meta.data, notifierType]);

  if (user?.onboarding_completed_at) {
    return <Navigate to="/app/searches" replace />;
  }

  const stepIndex = STEPS.findIndex((item) => item.key === step);

  async function finishOnboarding(destination = "/app/jobs") {
    await api.completeOnboarding();
    await refreshUser();
    navigate(destination, { replace: true });
  }

  async function skipSetup() {
    setBusy(true);
    setError(undefined);
    try {
      await finishOnboarding("/app/searches");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function detectFromUrl(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setBusy(true);
    try {
      const detected = await api.detectSource(detectUrl.trim());
      setSourceName(detected.suggested_name);
      setAdapterKey(detected.adapter_key);
      setBaseUrl(detected.base_url);
      setQueryUrl(detected.query_url);
      setSearchName(detected.suggested_name);
      setNotice(`Detected ${detected.adapter_key} board for ${detected.suggested_name}.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createSourceStep(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setNotice(undefined);
    if (!sourceName.trim() || !baseUrl.trim()) {
      setError("Name and base URL are required.");
      return;
    }
    setBusy(true);
    try {
      const source = await createSource.mutateAsync({
        name: sourceName.trim(),
        adapter_key: effectiveAdapter,
        base_url: baseUrl.trim(),
        default_config: {},
        enabled: true,
      });
      setSourceId(source.id);
      if (!searchName) setSearchName(source.name);
      if (!queryUrl) setQueryUrl(source.base_url);
      setStep("target");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createTargetStep(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setNotice(undefined);
    if (!targetName.trim()) {
      setError("Give your notification channel a name.");
      return;
    }
    setBusy(true);
    try {
      const target = await createTarget.mutateAsync({
        name: targetName.trim(),
        type: effectiveNotifier,
        config: notifierConfig,
      });
      setTargetId(target.id);
      setStep("search");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createSearchStep(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setNotice(undefined);
    if (sourceId == null || targetId == null) {
      setError("Complete the previous steps first.");
      return;
    }
    if (!searchName.trim() || !queryUrl.trim()) {
      setError("Search name and query URL are required.");
      return;
    }
    setBusy(true);
    try {
      const filters = keywords.trim() ? { keywords: keywords.trim() } : {};
      const search = await createSearch.mutateAsync({
        name: searchName.trim(),
        source_id: sourceId,
        target_id: targetId,
        query_url: queryUrl.trim(),
        filters,
        config: {},
        interval_seconds: 900,
        notification_mode: "immediate",
        digest_interval_seconds: 3600,
        enabled: true,
      });
      setSearchId(search.id);
      setStep("run");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runFirstSearch() {
    if (searchId == null) return;
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      const result = await runSearch.mutateAsync(searchId);
      if (result.error) {
        setError(`Scrape failed: ${result.error}`);
        return;
      }
      setNotice(
        `Found ${result.found} posting(s), ${result.new} new, ${result.notified} notified.` +
          (result.filtered ? ` ${result.filtered} filtered out.` : ""),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function completeSetup() {
    setBusy(true);
    setError(undefined);
    try {
      await finishOnboarding("/app/jobs");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onNotifierTypeChange(nextType: string) {
    setNotifierType(nextType);
    setNotifierConfig(NOTIFIER_DEFAULTS[nextType] ?? {});
  }

  function renderNotifierFields() {
    if (effectiveNotifier === "ntfy") {
      return (
        <>
          <Field label="ntfy topic" hint={NOTIFIER_HINTS.ntfy}>
            <input
              value={String(notifierConfig.topic ?? "")}
              onChange={(e) => setNotifierConfig({ ...notifierConfig, topic: e.target.value })}
              placeholder="my-job-alerts"
              required
            />
          </Field>
          <Field label="Server URL">
            <input
              value={String(notifierConfig.server_url ?? "https://ntfy.sh")}
              onChange={(e) => setNotifierConfig({ ...notifierConfig, server_url: e.target.value })}
            />
          </Field>
        </>
      );
    }
    if (effectiveNotifier === "email") {
      return (
        <Field label="Recipient email" hint={NOTIFIER_HINTS.email}>
          <input
            type="email"
            value={String(notifierConfig.to ?? "")}
            onChange={(e) => setNotifierConfig({ ...notifierConfig, to: e.target.value })}
            placeholder="you@example.com"
            required
          />
        </Field>
      );
    }
    if (effectiveNotifier === "slack" || effectiveNotifier === "discord") {
      return (
        <Field label="Webhook URL" hint={NOTIFIER_HINTS[effectiveNotifier]}>
          <input
            value={String(notifierConfig.webhook_url ?? "")}
            onChange={(e) => setNotifierConfig({ ...notifierConfig, webhook_url: e.target.value })}
            placeholder="https://..."
            required
          />
        </Field>
      );
    }
    if (effectiveNotifier === "telegram") {
      return (
        <>
          <Field label="Bot token" hint={NOTIFIER_HINTS.telegram}>
            <input
              value={String(notifierConfig.bot_token ?? "")}
              onChange={(e) => setNotifierConfig({ ...notifierConfig, bot_token: e.target.value })}
              required
            />
          </Field>
          <Field label="Chat id">
            <input
              value={String(notifierConfig.chat_id ?? "")}
              onChange={(e) => setNotifierConfig({ ...notifierConfig, chat_id: e.target.value })}
              required
            />
          </Field>
        </>
      );
    }
    return (
      <Field label="Webhook URL" hint={NOTIFIER_HINTS.webhook}>
        <input
          value={String(notifierConfig.webhook_url ?? "")}
          onChange={(e) => setNotifierConfig({ ...notifierConfig, webhook_url: e.target.value })}
          placeholder="https://..."
          required
        />
      </Field>
    );
  }

  return (
    <div className="onboarding-screen">
      <div className="onboarding-shell">
        <Brand to="/app/onboarding" />

        <ol className="onboarding-steps" aria-label="Setup progress">
          {STEPS.map((item, index) => (
            <li
              key={item.key}
              className={index < stepIndex ? "done" : index === stepIndex ? "current" : undefined}
            >
              <span className="onboarding-step-num">{index + 1}</span>
              <span className="onboarding-step-label">{item.label}</span>
            </li>
          ))}
        </ol>

        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="info">{notice}</Banner>}

        {step === "welcome" && (
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
              <Button onClick={() => setStep("source")}>Get started</Button>
              <Button variant="ghost" onClick={skipSetup} disabled={busy}>
                Skip for now
              </Button>
            </div>
          </Card>
        )}

        {step === "source" && (
          <Card title="Add a job board">
            <p className="onboarding-lead">
              Paste a careers or search URL and we will try to detect the board automatically.
            </p>
            <form onSubmit={detectFromUrl} className="onboarding-detect">
              <Field label="Careers or search URL">
                <input
                  value={detectUrl}
                  onChange={(e) => setDetectUrl(e.target.value)}
                  placeholder="https://boards.greenhouse.io/acme"
                />
              </Field>
              <Button type="submit" variant="ghost" disabled={busy || !detectUrl.trim()}>
                Detect board
              </Button>
            </form>

            <form onSubmit={createSourceStep}>
              <div className="form-grid">
                <Field label="Display name">
                  <input
                    value={sourceName}
                    onChange={(e) => setSourceName(e.target.value)}
                    placeholder="ACME Careers"
                    required
                  />
                </Field>
                <Field label="Scraper">
                  <select value={effectiveAdapter} onChange={(e) => setAdapterKey(e.target.value)}>
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
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://boards.greenhouse.io/acme"
                    required
                  />
                </Field>
              </div>
              <div className="onboarding-actions">
                <Button type="button" variant="ghost" onClick={() => setStep("welcome")}>
                  Back
                </Button>
                <Button type="submit" disabled={busy}>
                  Continue
                </Button>
              </div>
            </form>
          </Card>
        )}

        {step === "target" && (
          <Card title="Where should alerts go?">
            <p className="onboarding-lead">
              Pick a channel. You can add more targets later from Notifications.
            </p>
            <form onSubmit={createTargetStep}>
              <div className="form-grid">
                <Field label="Name">
                  <input
                    value={targetName}
                    onChange={(e) => setTargetName(e.target.value)}
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
                {renderNotifierFields()}
              </div>
              <div className="onboarding-actions">
                <Button type="button" variant="ghost" onClick={() => setStep("source")}>
                  Back
                </Button>
                <Button type="submit" disabled={busy}>
                  Continue
                </Button>
              </div>
            </form>
          </Card>
        )}

        {step === "search" && (
          <Card title="Create your first search">
            <p className="onboarding-lead">
              This is the query HeadStart will poll on a schedule. You can refine filters later.
            </p>
            <form onSubmit={createSearchStep}>
              <div className="form-grid">
                <Field label="Search name">
                  <input
                    value={searchName}
                    onChange={(e) => setSearchName(e.target.value)}
                    placeholder="Backend engineer roles"
                    required
                  />
                </Field>
                <Field label="Query URL">
                  <input
                    value={queryUrl}
                    onChange={(e) => setQueryUrl(e.target.value)}
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
                    onChange={(e) => setKeywords(e.target.value)}
                    placeholder="engineer backend"
                  />
                </Field>
              </div>
              <div className="onboarding-actions">
                <Button type="button" variant="ghost" onClick={() => setStep("target")}>
                  Back
                </Button>
                <Button type="submit" disabled={busy}>
                  Continue
                </Button>
              </div>
            </form>
          </Card>
        )}

        {step === "run" && (
          <Card title="Run your first check">
            <p className="onboarding-lead">
              We will scrape the board now and send any new matches to your notification channel.
            </p>
            <div className="onboarding-actions">
              <Button onClick={runFirstSearch} disabled={busy || searchId == null}>
                {busy ? "Running..." : "Run now"}
              </Button>
              <Button onClick={completeSetup} disabled={busy}>
                Go to Jobs
              </Button>
            </div>
            <p className="onboarding-footnote">
              Your search will keep polling every 15 minutes. Adjust interval and filters on the
              Searches page any time.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
