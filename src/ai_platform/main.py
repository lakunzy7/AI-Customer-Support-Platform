from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_platform.api import chat, health, rag
from ai_platform.config import settings
from ai_platform.core.logging import setup_logging
from ai_platform.core.middleware import RequestIDMiddleware, TimingMiddleware
from ai_platform.dependencies import close_clients

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
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
app.include_router(rag.router)
