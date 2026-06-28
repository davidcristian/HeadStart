# Getting started: from zero to your first job notification

This is the end-to-end walkthrough for a **user** who wants to start getting
notified when new jobs are posted on their preferred portals. It assumes you are
running the stack locally; the steps are identical against an AWS deployment,
only the URLs change.

By the end you will have: an account, a notification channel on your phone, a
source, a search, and a real push notification.

---

## 1. Start the stack

Prerequisites: Docker + Docker Compose.

```bash
cp .env.example .env     # edit NTFY_DEFAULT_TOPIC to something unguessable
make up                  # build + start api, worker, beat, db, redis, frontend
make migrate             # create the database tables
make seed                # optional: a demo account + example source/search
```

Open the UI at <http://localhost:8080> and the API docs at
<http://localhost:8000/docs>.

## 2. Create your account

Multi-user: every person has their own sources, searches, targets, and
credentials. Nothing is shared.

1. Open <http://localhost:8080>. You will be redirected to **Sign in**.
2. Click **Create one** and register with an email + password (min 8 chars).
3. The **first** account created on a fresh install becomes the **admin**.

> Ran `make seed`? A demo account already exists
> (`SEED_USER_EMAIL` / `SEED_USER_PASSWORD` from `.env`). You can log in with it,
> but create your own and change the password.

You are now signed in. Your session uses short-lived access tokens that refresh
automatically; click **Sign out** in the sidebar to end it.

## 3. Set up notifications on your phone (ntfy)

1. Install the **ntfy** app ([iOS](https://apps.apple.com/app/ntfy/id1625396347) /
   [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)) or
   open <https://ntfy.sh> in any browser.
2. Pick a **topic** name that is unguessable (think of it as a password, e.g.
   `jobs-7f3a9c2b`). Anyone who knows the topic can read your notifications.
3. In the ntfy app, **subscribe** to that exact topic.

## 4. Create a notification target

In the UI, go to **Notifications**:

1. Create a target of type `ntfy`.
2. Set its config to your server + topic, for example:

   ```json
   { "server_url": "https://ntfy.sh", "topic": "jobs-7f3a9c2b", "priority": "default" }
   ```

3. Click **Send test**. You should get a push on your phone within a second or
   two. If not, see [Troubleshooting](#troubleshooting).

## 5. Add a source (the job site)

Go to **Sources** and add the job site you want to watch. A source pairs a site
with a **scraper adapter**. Built-in adapters:

| Adapter        | Use it for                                                          |
| -------------- | ------------------------------------------------------------------- |
| `greenhouse`   | Companies hosted on Greenhouse job boards (JSON API, most reliable) |
| `generic_html` | Any HTML listing page, configured with CSS selectors               |
| `playwright`   | JavaScript-heavy pages that need a real browser (optional extra)    |

Example (Greenhouse): set adapter `greenhouse`, base URL the company board URL,
and default config:

```json
{ "board_token": "examplecorp", "company": "ExampleCorp" }
```

See [modules/scrapers.md](modules/scrapers.md) for each adapter's config keys.

## 6. (Optional) Add site credentials to bypass bot walls

Some portals hide listings behind a login or bot/captcha check. You can attach a
logged-in browser session to a source so the scraper is treated as you. See the
dedicated guide: [modules/credentials.md](modules/credentials.md). In short:

1. Log into the site in your browser, copy the relevant cookies/headers.
2. In the UI go to **Site credentials**, pick the source, paste the cookies
   and/or headers as JSON, and save.

Secrets are encrypted at rest and are never shown again after saving.

## 7. Create a search

Go to **Searches** and create one:

- **Source:** the one you just added.
- **Target:** the ntfy target from step 4.
- **Query URL / filters / config:** the specific query for this source (e.g. a
  role + location). Defaults from the source are merged with these.
- **Interval:** how often to poll (e.g. every 900 seconds).
- **Enabled:** on.

The search becomes **due immediately**, so the scheduler picks it up on the next
tick. You can also click **Run now**.

## 8. Get notified

- The **first** run records everything currently posted as "seen" — you will not
  be spammed with the whole back catalogue.
- From then on, only **newly posted** jobs trigger a push to your phone, with the
  job title and a tap-through link.
- Browse everything discovered so far on the **Jobs** page.

That's it — you're now watching that portal. Repeat steps 5–7 for every
site/role you care about (e.g. "Google SWE in Amsterdam", "Microsoft PM in Dublin").

---

## Troubleshooting

| Symptom                          | Fix                                                                   |
| -------------------------------- | --------------------------------------------------------------------- |
| Redirected to login repeatedly   | Token expired or backend unreachable; check the API URL in **Settings** |
| Test notification never arrives  | Topic mismatch — the target's `topic` must equal your ntfy subscription |
| Search never runs                | It is disabled, or `next_run_at` is in the future; use **Run now**    |
| A source returns nothing         | Wrong adapter/config; verify against [modules/scrapers.md](modules/scrapers.md) |
| Site needs login                 | Add **Site credentials** ([modules/credentials.md](modules/credentials.md)) |

More operational detail (logs, database, offline ntfy) is in
[runbook.md](runbook.md).
