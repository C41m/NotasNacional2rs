from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from app.core.config import settings
from app.models.base import Base
from datetime import datetime

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    connect_args={"ssl": "require"}
)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with async_session_factory() as session:
        yield session

@event.listens_for(Base, "before_update", propagate=True)
def set_updated_at(mapper, connection, target):
    """Auto-update updated_at on all models."""
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.utcnow()
