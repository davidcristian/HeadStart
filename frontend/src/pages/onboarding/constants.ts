/** Onboarding wizard step labels and notifier defaults. */

import type { Json } from "../../types";
import type { Step } from "./types";

export const STEPS: { key: Step; label: string }[] = [
  { key: "welcome", label: "Welcome" },
  { key: "source", label: "Source" },
  { key: "target", label: "Notify" },
  { key: "search", label: "Search" },
  { key: "run", label: "Run" },
];

export const NOTIFIER_DEFAULTS: Record<string, Json> = {
  // Pre-fill a high-entropy topic so onboarding never submits a guessable channel (NTF-06).
  ntfy: {
    server_url: "https://ntfy.sh",
    topic: `jobs-${crypto.randomUUID().replaceAll("-", "").slice(0, 16)}`,
    priority: "default",
  },
  email: { to: "" },
  slack: { webhook_url: "" },
  discord: { webhook_url: "" },
  telegram: { bot_token: "", chat_id: "" },
  webhook: { webhook_url: "" },
};

export const NOTIFIER_HINTS: Record<string, string> = {
  ntfy: "Topic is a secret (≥16 chars). Subscribe in the ntfy app or at ntfy.sh/<topic>; optional auth token recommended.",
  email: "Requires SMTP_* env vars on the server.",
  slack: "Paste an incoming webhook URL from your Slack workspace.",
  discord: "Paste a channel webhook URL from your Discord server.",
  telegram: "Use a bot token from @BotFather and your chat id.",
  webhook: "HTTPS endpoint that receives a JSON payload per job.",
};
