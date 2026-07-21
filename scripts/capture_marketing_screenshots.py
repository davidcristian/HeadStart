#!/usr/bin/env python3
"""Capture marketing screenshots from a running local dev stack.

Requires `just dev` (or equivalent) on :5173 with API on :8000, plus Playwright
with Chromium (`pip install playwright && playwright install chromium`).

Seeds rich demo rows for the seed user, logs in through the UI, and writes
PNG images to frontend/public/marketing/.

Run via: `./scripts/capture_marketing_screenshots.py`
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "marketing"

FRONTEND_URL = "http://localhost:5173"
SEED_EMAIL = "demo@example.com"
SEED_PASSWORD = "demo-password-change-me"

DEMO_JOBS = [
    {
        "external_id": "marketing-senior-backend",
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "location": "Remote · US",
        "salary": "$180k to $210k",
        "url": "https://boards.greenhouse.io/example/jobs/1001",
        "summary": "Matches your Kubernetes and Python filters; remote-first team.",
        "status": "new",
    },
    {
        "external_id": "marketing-staff-platform",
        "title": "Staff Platform Engineer",
        "company": "Northwind Labs",
        "location": "Amsterdam · Hybrid",
        "salary": "€85k to €100k",
        "url": "https://jobs.lever.co/example/staff-platform",
        "summary": "Includes “kubernetes” and platform ownership keywords.",
        "status": "seen",
    },
    {
        "external_id": "marketing-product-engineer",
        "title": "Product Engineer",
        "company": "Brightside",
        "location": "London · Hybrid",
        "salary": "£95k to £115k",
        "url": "https://jobs.ashbyhq.com/example/product-engineer",
        "summary": "Full-stack role with product surface area; hybrid 2 days/week.",
        "status": "applied",
    },
]


def _content_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def seed_marketing_demo() -> None:
    """Insert demo search health + jobs for screenshot-friendly UI state."""
    from sqlalchemy import delete, select

    from app.core.config import settings
    from app.core.db import session_scope
    from app.models.base import utcnow
    from app.models.seen_job import SeenJob
    from app.models.search import Search
    from app.models.user import User

    email = settings.seed_user_email.lower()
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            raise RuntimeError(f"Seed user {email} not found. Run `just seed` first.")

        search = session.scalar(
            select(Search)
            .where(Search.user_id == user.id)
            .where(Search.name == "Example - all jobs")
        )
        if search is None:
            raise RuntimeError("Example search missing. Run `just seed` first.")

        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = utcnow()

        search.enabled = True
        search.last_run_at = utcnow()
        search.last_error = ""
        search.notification_mode = "immediate"

        session.execute(delete(SeenJob).where(SeenJob.search_id == search.id))
        for job in DEMO_JOBS:
            session.add(
                SeenJob(
                    search_id=search.id,
                    external_id=job["external_id"],
                    hash=_content_hash(job["url"]),
                    title=job["title"],
                    company=job["company"],
                    location=job["location"],
                    salary=job["salary"],
                    url=job["url"],
                    summary=job["summary"],
                    status=job["status"],
                )
            )


def _login(page) -> None:
    page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
    page.get_by_label("Email").fill(SEED_EMAIL)
    page.get_by_label("Password").fill(SEED_PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/app/**", timeout=15_000)


def _dismiss_cookie_banner(page) -> None:
    """The consent banner would otherwise overlay every capture."""
    try:
        page.get_by_role("button", name="Essential only").click(timeout=3_000)
        page.wait_for_timeout(300)
    except Exception:
        pass


def _capture(page, path: str, outfile: Path) -> None:
    page.goto(f"{FRONTEND_URL}{path}", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.locator(".layout").screenshot(path=str(outfile), type="png")


def _capture_notification_card(page, outfile: Path) -> None:
    """Render the landing notification mock as a standalone marketing asset."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <link rel="stylesheet" href="http://localhost:5173/src/index.css" />
      <style>
        body {
          margin: 0;
          min-height: 100vh;
          display: grid;
          place-items: center;
          background: #09090b;
          font-family: "Inter", system-ui, sans-serif;
        }
        .card {
          width: 320px;
          background: rgba(19, 19, 22, 0.95);
          border: 1px solid rgba(52, 211, 153, 0.35);
          border-radius: 16px;
          padding: 18px;
          box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
          color: #e8edf4;
        }
        .label {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #34d399;
          margin-bottom: 8px;
        }
        strong { display: block; font-size: 18px; margin-bottom: 6px; }
        .meta { display: block; font-size: 13px; color: #a1a1aa; margin-bottom: 10px; }
        .pill {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 999px;
          background: rgba(52, 211, 153, 0.15);
          color: #6ee7b7;
          font-size: 12px;
          font-weight: 600;
        }
        .summary {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #2a2a31;
          font-size: 13px;
          color: #b8c5d6;
          line-height: 1.5;
        }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="label">New match · ntfy</div>
        <strong>Senior Backend Engineer</strong>
        <span class="meta">Acme Corp · Remote · $180k to $210k</span>
        <span class="pill">Just posted</span>
        <p class="summary">Matches your Kubernetes and Python filters; remote-first team.</p>
      </div>
    </body>
    </html>
    """
    page.set_content(html, wait_until="load")
    page.wait_for_timeout(200)
    page.locator(".card").screenshot(path=str(outfile), type="png")


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("==> Seeding marketing demo data")
    seed_marketing_demo()

    shots = {
        "searches.png": "/app/searches",
        "jobs.png": "/app/jobs",
    }

    print("==> Capturing screenshots (Playwright)")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme="dark")
        _login(page)
        _dismiss_cookie_banner(page)
        for filename, path in shots.items():
            outfile = OUTPUT_DIR / filename
            print(f"    {filename}")
            _capture(page, path, outfile)
        notify_out = OUTPUT_DIR / "notification.png"
        print("    notification.png")
        _capture_notification_card(page, notify_out)
        browser.close()

    print(f"OK  Wrote {len(shots) + 1} images to {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
