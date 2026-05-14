import sys
import asyncio
import logging
import urllib.request

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine
from app.api.routers.companies import router as companies_router
from app.api.routers.nfse import router as nfse_router
import structlog

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.JSONRenderer()
])

logger = logging.getLogger("keepalive")

# ── Keepalive interno para evitar que o Render durma por inatividade ──
async def _self_ping(stop_event: asyncio.Event, base_url: str):
    """Task async que pinga o próprio servidor periodicamente usando thread pool."""
    health_url = f"{base_url.rstrip('/')}/health"
    while not stop_event.is_set():
        try:
            # Usa to_thread para não bloquear o event loop
            await asyncio.to_thread(
                urllib.request.urlopen, health_url, 10
            )
            logger.info("Self-ping OK")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        # Pinga a cada 5 minutos (antes do timeout de 15 min do Render free tier)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300)
            break
        except asyncio.TimeoutError:
            pass

_ping_task: asyncio.Task | None = None
_ping_stop_event: asyncio.Event | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ping_task, _ping_stop_event
    _ping_stop_event = asyncio.Event()
    base_url = f"http://127.0.0.1:{settings.PORT}"
    logger.info(f"Iniciando keepalive self-ping em {base_url}")
    _ping_task = asyncio.create_task(_self_ping(_ping_stop_event, base_url))
    yield
    logger.info("Encerrando keepalive...")
    _ping_stop_event.set()
    if _ping_task:
        _ping_task.cancel()
        try:
            await _ping_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()

app = FastAPI(title="NFSe Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

app.include_router(companies_router)
app.include_router(nfse_router)
