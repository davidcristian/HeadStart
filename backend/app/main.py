"""FastAPI application factory."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings, settings
from app.core.exceptions import ConflictError, NotFoundError, PlanLimitError, ValidationError
from app.core.logging import configure_logging
from app.core.metrics import render_metrics

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="HeadStart API",
        version=__version__,
        summary="Configure job-site searches and get notified about new postings.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=API_PREFIX)
    _register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "HeadStart API", "docs": "/docs", "health": f"{API_PREFIX}/health"}

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        """Prometheus scrape endpoint (API process metrics)."""
        cfg = get_settings()
        if not cfg.metrics_enabled:
            return Response(status_code=404)
        if cfg.metrics_token:
            auth = request.headers.get("Authorization", "")
            expected = f"Bearer {cfg.metrics_token}"
            if auth != expected:
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


app = create_app()
