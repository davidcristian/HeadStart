# 0001. Tech stack: FastAPI + React + Celery

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

We need a modular full-stack app that scrapes job sites on a schedule and pushes
notifications. The team wants standard practices, clean module boundaries, and a
codebase that autonomous agents can extend cheaply.

## Decision

- **Backend:** Python 3.12 + FastAPI. Python has the strongest scraping ecosystem
  (httpx, selectolax, Playwright) and FastAPI gives typed, documented APIs with
  Pydantic v2.
- **Frontend:** React + TypeScript (Vite). Ubiquitous, strongly typed, fast dev
  loop, easy to containerize behind nginx.
- **Scheduling/async work:** Celery (beat + workers) over Redis. Cleanly splits
  "when to poll" from "do the work" and scales horizontally.
- **Database:** Postgres via SQLAlchemy 2.0 + Alembic migrations.

## Consequences

- Two languages (Python + TS) but each is best-in-class for its half.
- Celery + Redis adds a broker dependency, justified by reliable scheduling and
  retry semantics.
- Clear layering (api -> services -> repositories -> models) enforced in
  [AGENTS.md](../../AGENTS.md).

## Alternatives considered

- **TypeScript everywhere (Node backend):** one language, but weaker scraping
  story (especially anti-bot/Playwright ergonomics and HTML parsing).
- **APScheduler instead of Celery:** simpler, but weaker distributed/retry
  semantics and no clean worker scaling.
