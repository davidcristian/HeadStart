# Backend image. One image runs the API, worker, or beat (see docker-entrypoint.sh).
# Targets:
#   api    (default) — lean image without Playwright
#   worker           — includes Chromium for the playwright scraper adapter

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first (better layer caching). psycopg[binary] and
# selectolax ship wheels, so no compiler/system libs are required.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Migrations + entrypoint.
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser /app

FROM base AS worker

# Playwright + Chromium for JS-heavy scrapes. Needs root for system deps.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install ".[playwright]" \
    && playwright install --with-deps chromium \
    && chown -R appuser:appuser /ms-playwright

USER appuser

EXPOSE 8000 9090
ENTRYPOINT ["entrypoint.sh"]
CMD ["worker"]

FROM base AS api

USER appuser

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["api"]
