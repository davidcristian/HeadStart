/** State and handlers for the first-run onboarding wizard. */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth/AuthContext";
import { useMeta } from "../../hooks/queries";
import {
  useCreateSearch,
  useCreateSource,
  useCreateTarget,
  useRunSearch,
} from "../../hooks/mutations";
import type { Json } from "../../types";
import { NOTIFIER_DEFAULTS, STEPS } from "./constants";
import type { Step } from "./types";

export function useOnboardingWizard() {
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
  const stepIndex = STEPS.findIndex((item) => item.key === step);

  useEffect(() => {
    if (!meta.data?.notifiers.length || notifierType) return;
    // Length checked above; prefer ntfy when present, else the first adapter key.
    const initial = meta.data.notifiers.includes("ntfy") ? "ntfy" : meta.data.notifiers[0]!;
    setNotifierType(initial);
    setNotifierConfig(NOTIFIER_DEFAULTS[initial] ?? {});
  }, [meta.data, notifierType]);

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

  return {
    user,
    step,
    setStep,
    stepIndex,
    error,
    notice,
    busy,
    searchId,
    detectUrl,
    setDetectUrl,
    sourceName,
    setSourceName,
    adapterKey,
    setAdapterKey,
    baseUrl,
    setBaseUrl,
    queryUrl,
    setQueryUrl,
    targetName,
    setTargetName,
    effectiveNotifier,
    notifierConfig,
    setNotifierConfig,
    searchName,
    setSearchName,
    keywords,
    setKeywords,
    adapters,
    notifiers,
    effectiveAdapter,
    skipSetup,
    detectFromUrl,
    createSourceStep,
    createTargetStep,
    createSearchStep,
    runFirstSearch,
    completeSetup,
    onNotifierTypeChange,
  };
}
