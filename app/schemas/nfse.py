from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import List

class NFSEDownloadRequest(BaseModel):
    company_id: int = Field(..., gt=0)

class NFSEDownloadResponse(BaseModel):
    job_id: str
    status: str

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class NFSEDownloadStatus(BaseModel):
    job_id: str
    status: JobStatus
    file_url: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BatchDownloadRequest(BaseModel):
    company_ids: List[int] = Field(..., min_length=1)
    datainicio: str = Field(..., pattern=r"\d{2}/\d{2}/\d{4}")
    datafim: str = Field(..., pattern=r"\d{2}/\d{2}/\d{4}")
