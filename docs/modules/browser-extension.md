# Module: Browser extension

**Path:** `browser-extension/`

Chrome extension (Manifest V3) that adds a job board from the current browser
tab to HeadStart in one click.

## What it does

1. Read the active tab URL (Greenhouse, Lever, Ashby, or Workday careers pages).
2. Call `POST /api/v1/sources/detect` to infer the scraper adapter and defaults.
3. Create a **source** (and optionally a **search**) via the authenticated API.

Unsupported pages show an error — use the web UI with `generic_html` or
`playwright` for other sites.

## Install (development)

```bash
cd browser-extension
npm install
npm run build
```

Load the unpacked extension in Chrome:

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select `browser-extension/dist`

Sign in with the same email/password as the web app. Set **API URL** (backend,
e.g. `http://localhost:8000`) and **App URL** (frontend, e.g.
`http://localhost:5173`).

## Usage

1. Open a supported careers page (e.g. `https://jobs.lever.co/<company>`).
2. Click the HeadStart toolbar icon.
3. Review the detected adapter and name, then click **Add to HeadStart**.
4. Optionally keep **Also create a search** checked to start polling immediately
   (assign a notification target in the web app afterward).

## API

The extension uses existing auth and CRUD endpoints plus:

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/v1/sources/detect` | Infer adapter + defaults from a tab URL |

Detection logic lives in `backend/app/scrapers/url_detect.py` (single source of
truth shared with any future UI helpers).

## Permissions

- `storage` — persist API URL and JWT tokens locally in the browser
- `tabs` / `activeTab` — read the current tab URL and title
- `host_permissions` — call your HeadStart API (`http://localhost/*` and
  `https://*/*`)

Tokens are stored in `chrome.storage.local` only; they are never synced to
HeadStart servers beyond normal API requests.

## Tests

```bash
cd browser-extension && npm test
```

Also runs as part of `make test` when `browser-extension/node_modules` exists.
