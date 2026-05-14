import sys
import asyncio

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

# Keepalive gerenciado pelo UptimeRobot (https://uptimerobot.com)
# O self-ping em localhost não conta como tráfego externo no Render free tier.

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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

@app.head("/health")
async def health_head():
    return {"status": "healthy"}

app.include_router(companies_router)
app.include_router(nfse_router)