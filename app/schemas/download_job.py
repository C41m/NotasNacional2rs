from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import Literal


class DownloadJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class DownloadJobBase(BaseModel):
    company_id: int = Field(..., gt=0)
    status: DownloadJobStatus = DownloadJobStatus.QUEUED
    file_url: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_registros: int | None = None
    notas_processed: int = 0
    data_inicio: str | None = Field(None, pattern=r"\d{2}/\d{2}/\d{4}")
    data_fim: str | None = Field(None, pattern=r"\d{2}/\d{2}/\d{4}")
    download_type: Literal["xml", "pdf", "both"] = "xml"


class DownloadJobCreate(BaseModel):
    company_id: int = Field(..., gt=0)
    data_inicio: str = Field(..., pattern=r"\d{2}/\d{2}/\d{4}")
    data_fim: str = Field(..., pattern=r"\d{2}/\d{2}/\d{4}")
    download_type: Literal["xml", "pdf", "both"] = "xml"


class DownloadJobUpdate(BaseModel):
    status: DownloadJobStatus | None = None
    file_url: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_registros: int | None = None
    notas_processed: int | None = None


class DownloadJobOut(BaseModel):
    id: str
    company_id: int
    status: DownloadJobStatus
    file_url: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_registros: int | None = None
    notas_processed: int = 0
    data_inicio: str | None = None
    data_fim: str | None = None
    download_type: str = "xml"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
