import sys
import asyncio
import threading
import time
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

# ── Keepalive interno para evitar que o Render durma por inatividade ──
def _self_ping(base_url: str, stop_event: threading.Event):
    """Thread que pinga o próprio servidor periodicamente."""
    health_url = f"{base_url.rstrip('/')}/health"
    while not stop_event.is_set():
        try:
            urllib.request.urlopen(health_url, timeout=10)
        except Exception:
            pass
        # Pinga a cada 10 minutos (antes do timeout de 15 min do Render free tier)
        stop_event.wait(600)

_ping_stop_event: threading.Event | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ping_stop_event
    _ping_stop_event = threading.Event()
    # Usa a mesma porta configurada no settings (default 8000)
    base_url = f"http://localhost:{settings.PORT}"
    # Inicia o self-ping em thread separada
    t = threading.Thread(
        target=_self_ping,
        args=(base_url, _ping_stop_event),
        daemon=True,
    )
    t.start()
    yield
    _ping_stop_event.set()
    t.join(timeout=5)
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
