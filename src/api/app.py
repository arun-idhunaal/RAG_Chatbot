"""FastAPI app: GET /health, GET /v1/ui-config, POST /v1/chat; serve React dist in prod."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.dto import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    UiConfigResponse,
    corpus_unavailable_response,
    pipeline_result_to_chat_response,
    ui_config,
)
from src.api.ingest_job import ingest_status, try_start_ingest
from src.config.settings import Settings, get_settings
from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE, HealthStatus, check_index_health
from src.ops.metrics import record_query_metric
from src.pipeline.orchestrator import process_query
from src.retrieval.retriever import Retriever

HealthFn = Callable[[], HealthStatus]


def create_app(
    *,
    settings: Settings | None = None,
    retriever: Retriever | None = None,
    health_fn: HealthFn | None = None,
    load_retriever: bool = True,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_retriever and retriever is None:
            app.state.retriever = Retriever(settings=settings)
        else:
            app.state.retriever = retriever
        # Render: never block listen/health on ingest. Refresh empty index in-process.
        if settings.auto_ingest_on_empty:
            status = check_index_health(settings=settings, run_sample_query=False)
            if not status.ok:
                try_start_ingest(app, settings=settings)
        yield

    application = FastAPI(
        title="INDmoney MF FAQ",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.health_fn = health_fn or (
        lambda: check_index_health(settings=settings, run_sample_query=True)
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        status: HealthStatus = application.state.health_fn()
        return HealthResponse(
            ok=status.ok,
            corpus_available=status.ok,
            scheme_count=status.scheme_count,
            general_count=status.general_count,
            reason=status.reason,
            message=None if status.ok else CORPUS_UNAVAILABLE_MESSAGE,
        )

    @application.get("/v1/ui-config", response_model=UiConfigResponse)
    def get_ui_config() -> UiConfigResponse:
        return ui_config()

    @application.post("/v1/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        status: HealthStatus = application.state.health_fn()
        if not status.ok:
            record_query_metric(
                intent="unavailable",
                empty_hit=True,
                short_circuit=True,
            )
            return corpus_unavailable_response()

        t0 = time.perf_counter()
        result = process_query(
            body.message,
            settings=settings,
            retriever=application.state.retriever,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        record_query_metric(
            intent=result.intent.value,
            empty_hit=bool(result.retrieval_empty or result.insufficient_context),
            citation_validation_failed=False,
            short_circuit=bool(result.short_circuit),
            latency_ms=latency_ms,
        )
        return pipeline_result_to_chat_response(result)

    @application.post("/v1/admin/ingest")
    def admin_ingest(request: Request) -> JSONResponse:
        """Token-gated refresh so Render's disk can be updated (GitHub Action / dashboard)."""
        token = (settings.ingest_token or "").strip()
        if not token:
            raise HTTPException(status_code=404, detail="Not found")
        auth = request.headers.get("authorization") or ""
        if auth != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Unauthorized")
        started = try_start_ingest(application, settings=settings)
        return JSONResponse(
            status_code=202,
            content={"accepted": True, "started": started, **ingest_status()},
        )

    _mount_spa(application, settings.web_dist_dir)
    return application


def _mount_spa(application: FastAPI, dist: Path) -> None:
    if not dist.is_dir() or not (dist / "index.html").is_file():
        return

    assets = dist / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(dist / "index.html")

    @application.get("/{path:path}")
    def spa_fallback(request: Request, path: str) -> Any:
        del request
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
