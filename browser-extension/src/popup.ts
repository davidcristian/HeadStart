/** Popup UI: detect the active tab and create a source (+ optional search). */

import { createSearch, createSource, detectSource, login } from "./api";
import { clearSession, defaultApiBaseUrl, defaultAppBaseUrl, loadSession, saveSession } from "./storage";
import type { Session, SourceDetectResult } from "./types";
import { ApiError } from "./types";

type View = "login" | "detect" | "form" | "success";

const loginView = document.querySelector<HTMLElement>("#login-view")!;
const detectView = document.querySelector<HTMLElement>("#detect-view")!;
const formView = document.querySelector<HTMLElement>("#form-view")!;
const successView = document.querySelector<HTMLElement>("#success-view")!;
const errorEl = document.querySelector<HTMLElement>("#error")!;
const logoutBtn = document.querySelector<HTMLButtonElement>("#logout-btn")!;

const apiUrlInput = document.querySelector<HTMLInputElement>("#api-url")!;
const appUrlInput = document.querySelector<HTMLInputElement>("#app-url")!;
const emailInput = document.querySelector<HTMLInputElement>("#email")!;
const passwordInput = document.querySelector<HTMLInputElement>("#password")!;
const loginBtn = document.querySelector<HTMLButtonElement>("#login-btn")!;

const pageUrlEl = document.querySelector<HTMLElement>("#page-url")!;
const sourceNameInput = document.querySelector<HTMLInputElement>("#source-name")!;
const adapterKeyInput = document.querySelector<HTMLInputElement>("#adapter-key")!;
const createSearchCheckbox = document.querySelector<HTMLInputElement>("#create-search")!;
const createBtn = document.querySelector<HTMLButtonElement>("#create-btn")!;

const successMessageEl = document.querySelector<HTMLElement>("#success-message")!;
const openAppBtn = document.querySelector<HTMLButtonElement>("#open-app-btn")!;
const addAnotherBtn = document.querySelector<HTMLButtonElement>("#add-another-btn")!;

let session: Session | null = null;
let detection: SourceDetectResult | null = null;
let tabUrl = "";

function showView(view: View): void {
  loginView.hidden = view !== "login";
  detectView.hidden = view !== "detect";
  formView.hidden = view !== "form";
  successView.hidden = view !== "success";
  logoutBtn.hidden = view === "login";
}

function showError(message: string | null): void {
  if (!message) {
    errorEl.hidden = true;
    errorEl.textContent = "";
    return;
  }
  errorEl.hidden = false;
  errorEl.textContent = message;
}

async function getActiveTab(): Promise<chrome.tabs.Tab | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ?? null;
}

function applyDetection(result: SourceDetectResult, url: string): void {
  detection = result;
  tabUrl = url;
  pageUrlEl.textContent = url;
  sourceNameInput.value = result.suggested_name;
  adapterKeyInput.value = result.adapter_key;
  showView("form");
}

async function runDetect(activeSession: Session): Promise<void> {
  showView("detect");
  showError(null);
  const tab = await getActiveTab();
  const url = tab?.url ?? "";
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    showView("login");
    showError("Open a job board page in the active tab, then reopen this popup.");
    return;
  }
  try {
    const { data, session: updated } = await detectSource(
      activeSession,
      url,
      tab?.title ?? null,
    );
    session = updated;
    await saveSession(session);
    applyDetection(data, url);
  } catch (err) {
    showView("form");
    pageUrlEl.textContent = url;
    sourceNameInput.value = "";
    adapterKeyInput.value = "";
    detection = null;
    tabUrl = url;
    showError(err instanceof ApiError ? err.message : "Could not detect this job board.");
  }
}

async function bootstrap(): Promise<void> {
  apiUrlInput.value = defaultApiBaseUrl();
  appUrlInput.value = defaultAppBaseUrl();
  session = await loadSession();
  if (!session) {
    showView("login");
    return;
  }
  apiUrlInput.value = session.apiBaseUrl;
  appUrlInput.value = session.appBaseUrl;
  await runDetect(session);
}

loginBtn.addEventListener("click", async () => {
  showError(null);
  loginBtn.disabled = true;
  try {
    session = await login(
      apiUrlInput.value,
      emailInput.value,
      passwordInput.value,
      appUrlInput.value,
    );
    await saveSession(session);
    passwordInput.value = "";
    await runDetect(session);
  } catch (err) {
    showError(err instanceof ApiError ? err.message : "Sign in failed.");
  } finally {
    loginBtn.disabled = false;
  }
});

createBtn.addEventListener("click", async () => {
  if (!session || !detection) {
    return;
  }
  showError(null);
  createBtn.disabled = true;
  try {
    const name = sourceNameInput.value.trim();
    if (!name) {
      throw new Error("Name is required.");
    }
    const sourceResult = await createSource(session, {
      name,
      adapter_key: detection.adapter_key,
      base_url: detection.base_url,
      default_config: detection.default_config,
      enabled: true,
    });
    session = sourceResult.session;
    await saveSession(session);

    let message = `Source "${name}" created.`;
    if (createSearchCheckbox.checked) {
      const searchResult = await createSearch(session, {
        name: `${name} search`,
        source_id: sourceResult.data.id,
        query_url: detection.query_url,
        enabled: true,
        interval_seconds: 900,
      });
      session = searchResult.session;
      await saveSession(session);
      message = `Source and search created for "${name}".`;
    }

    successMessageEl.textContent = message;
    openAppBtn.onclick = () => {
      chrome.tabs.create({ url: `${session!.appBaseUrl}/searches` });
    };
    showView("success");
  } catch (err) {
    showError(err instanceof ApiError ? err.message : (err as Error).message);
  } finally {
    createBtn.disabled = false;
  }
});

addAnotherBtn.addEventListener("click", async () => {
  if (!session) {
    showView("login");
    return;
  }
  await runDetect(session);
});

logoutBtn.addEventListener("click", async () => {
  await clearSession();
  session = null;
  detection = null;
  showView("login");
  showError(null);
});

void bootstrap();
