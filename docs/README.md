# HeadStart Documentation

This folder is the **source of truth** for how the system works and how to work
on it. It is intentionally small and modular so you can load only the context you
need for a given task.

> Read this map, then open only the specific file(s) relevant to your task.
> Updating the doc that corresponds to any behavior you change is part of the
> Definition of Done (see [AGENTS.md](../AGENTS.md)).

## Map

| If you want to...                              | Read                                          |
| ---------------------------------------------- | --------------------------------------------- |
| Get notified for your first job (as a user)    | [getting-started.md](getting-started.md)      |
| Deploy the stack to AWS (first time)           | [deploying-to-aws.md](deploying-to-aws.md)    |
| Understand the system end-to-end               | [architecture.md](architecture.md)            |
| Know coding standards, naming, layering        | [conventions.md](conventions.md)              |
| Add a scraper / notifier / endpoint / migration| [recipes.md](recipes.md)        |
| Run, operate, or debug the running system      | [runbook.md](runbook.md)                      |
| Launch a hosted instance publicly              | [launch-checklist.md](launch-checklist.md)    |
| See planned work and priorities                | [roadmap.md](roadmap.md)                      |
| Monitor scrape/notify health (Prometheus)      | [modules/metrics.md](modules/metrics.md)      |
| Dev inbox / local application agent            | [modules/inbox.md](modules/inbox.md) + [runbook.md](runbook.md#local-application-agent-dev-only) |
| Configure Stripe billing / subscriptions       | [modules/billing.md](modules/billing.md)      |
| See the logo / brand asset explorations        | [branding/README.md](branding/README.md)      |
| Understand *why* a decision was made           | [adr/](adr/) (incl. [0012 lockfiles](adr/0012-backend-dependency-lockfiles.md)) |
| Dive into one module                           | [modules/](modules/)                          |
| Submit job applications (auto-apply)           | [modules/appliers.md](modules/appliers.md)    |
| Browse curated employer portals                | [modules/portals.md](modules/portals.md)      |
| Scraper adapters (Phenom, Rippling, IBM, …)    | [modules/scrapers.md](modules/scrapers.md)    |

## Module docs

Each subsystem has a focused doc. Open just the one you need.

| Module        | Doc                                            |
| ------------- | ---------------------------------------------- |
| Scrapers      | [modules/scrapers.md](modules/scrapers.md)     |
| Notifiers     | [modules/notifiers.md](modules/notifiers.md)   |
| Summaries (AI)| [modules/summaries.md](modules/summaries.md)   |
| API           | [modules/api.md](modules/api.md)               |
| Auth          | [modules/auth.md](modules/auth.md)             |
| Site credentials | [modules/credentials.md](modules/credentials.md) |
| Application profile | [modules/profile.md](modules/profile.md)    |
| Apply adapters      | [modules/appliers.md](modules/appliers.md)  |
| Curated portals     | [modules/portals.md](modules/portals.md)    |
| Worker/Scheduler | [modules/worker.md](modules/worker.md)      |
| Inbox (dev)   | [modules/inbox.md](modules/inbox.md)           |
| Metrics       | [modules/metrics.md](modules/metrics.md)       |
| Billing       | [modules/billing.md](modules/billing.md)       |
| Data model    | [modules/data-model.md](modules/data-model.md) |
| Frontend      | [modules/frontend.md](modules/frontend.md)     |
| Deployment    | [modules/deployment.md](modules/deployment.md) |

## Conventions for this folder

- One concern per file; keep each doc short and current.
- When code and docs disagree, the code is right and the doc is a bug you fix.
- Record notable decisions as a new file in [adr/](adr/) using
  [adr/0000-template.md](adr/0000-template.md).
