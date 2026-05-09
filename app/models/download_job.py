import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class DownloadJob(Base):
    __tablename__ = "download_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    file_url = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total_registros = Column(Integer, nullable=True)
    notas_processed = Column(Integer, nullable=True, default=0)
    data_inicio = Column(String(10), nullable=True)
    data_fim = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="download_jobs")
