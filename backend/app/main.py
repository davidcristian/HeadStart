"""FastAPI application factory."""

import hmac

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings, settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PlanLimitError,
    RateLimitError,
    ValidationError,
)
from app.core.logging import configure_logging
from app.core.metrics import render_metrics
from app.core.request_id import RequestIdMiddleware
from app.core.secret_policy import is_local_environment
from app.core.security_headers import SecurityHeadersMiddleware

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    configure_logging()
    # AUT-25: interactive OpenAPI UI is local/test only — prod must not enumerate routes.
    docs_enabled = is_local_environment(get_settings().environment)

    app = FastAPI(
        title="HeadStart API",
        version=__version__,
        summary="Configure job-site searches and get notified about new postings.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # Last add_middleware wins as outermost; CORS must wrap the app for preflight.
    # Security headers sit outside CORS so every response (incl. preflight) is stamped.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(api_router, prefix=API_PREFIX)
    _register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        payload: dict[str, str] = {
            "name": "HeadStart API",
            "health": f"{API_PREFIX}/health",
        }
        if docs_enabled:
            payload["docs"] = "/docs"
        return payload

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        """Prometheus scrape endpoint (API process metrics)."""
        cfg = get_settings()
        if not cfg.metrics_enabled:
            return Response(status_code=404)
        if cfg.metrics_token:
            auth = request.headers.get("Authorization", "")
            expected = f"Bearer {cfg.metrics_token}"
            if not hmac.compare_digest(auth.encode(), expected.encode()):
                return Response(status_code=401)
        body, content_type = render_metrics()
        return Response(content=body, media_type=content_type)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    def _validation(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PlanLimitError)
    def _plan_limit(_: Request, exc: PlanLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=402,
            content={
                "detail": str(exc),
                "code": exc.code,
                "plan": exc.plan,
                "limit": exc.limit,
            },
        )

    @app.exception_handler(RateLimitError)
    def _rate_limit(_: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})


app = create_app()
