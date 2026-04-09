from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_platform.api import chat, conversations, files, health, rag
from ai_platform.config import settings
from ai_platform.core.logging import setup_logging
from ai_platform.core.middleware import RequestIDMiddleware, TimingMiddleware
from ai_platform.dependencies import close_clients

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    try:
        from ai_platform.core.telemetry import setup_telemetry

        setup_telemetry(app)
        await logger.ainfo("telemetry_enabled")
    except ImportError:
        pass  # otel extras not installed
    await logger.ainfo("startup", env=settings.app_env)
    yield
    await logger.ainfo("shutdown")
    await close_clients()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(files.router)
app.include_router(rag.router)

# Prometheus metrics — FastAPI request instrumentation + /metrics endpoint
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except ImportError:
    pass  # prometheus-fastapi-instrumentator not installed

# Static files and chat UI
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
