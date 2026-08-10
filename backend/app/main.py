import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.api.v1.router import api_v1_router
from app.services import review_email_worker
from app.websockets.routes import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Startup: verify the database engine is reachable, start background workers.
    Shutdown: stop the workers, then dispose of the connection pool cleanly.
    """
    # Startup
    review_worker = asyncio.create_task(
        review_email_worker.run_review_email_worker()
    )
    try:
        yield
    finally:
        # Shutdown. Cancel and await, so the loop cannot still be holding a
        # connection when the pool is disposed below.
        review_worker.cancel()
        with suppress(asyncio.CancelledError):
            await review_worker
        await engine.dispose()


# Disable interactive docs in production
_docs_url = "/docs" if not settings.is_production else None
_redoc_url = "/redoc" if not settings.is_production else None

app = FastAPI(
    title="POS System API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")

# Mount WebSocket router (no prefix — /ws is at root)
app.include_router(ws_router)
