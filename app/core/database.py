from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.models.base import Base
from datetime import datetime

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    poolclass=NullPool
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@event.listens_for(Base, "before_update", propagate=True)
def set_updated_at(mapper, connection, target):
    """Auto-update updated_at on all models."""
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.utcnow()
