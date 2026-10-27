from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import List, Literal, Dict, Any


class NFSEDownloadRequest(BaseModel):
    company_id: int = Field(..., gt=0)


class NFSEDownloadResponse(BaseModel):
    batch_id: str
    status: str


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class CompanyProgressStatus(BaseModel):
    status: str
    notas_done: int = 0
    notas_salvas: int = 0
    valorServico: float = 0.0
    valorIss: float = 0.0
    notasPrestadas: int = 0
    notasTomadas: int = 0
    notasCanceladas: int = 0
    valorPrestado: float = 0.0
    valorTomado: float = 0.0
    valorCancelado: float = 0.0
    carregando_notas: bool = False
    cnpj: str = ""
    nome: str = ""
    id_dominio: int = 0
    empresa_id: int = 0
    mensagem: str = ""
    notas_total: int = 0
    error: str = ""

    model_config = ConfigDict(extra="allow", serialize_defaults=True)


class NFSEDownloadStatus(BaseModel):
    batch_id: str
    status: JobStatus
    file_url: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    total: int = 0
    done: int = 0
    companies: Dict[str, CompanyProgressStatus] = {}

    model_config = ConfigDict(from_attributes=True)


class BatchDownloadRequest(BaseModel):
    company_ids: List[int] = Field(..., min_length=1)
    datainicio: str | None = Field(None, pattern=r"\d{2}/\d{2}/\d{4}")
    datafim: str | None = Field(None, pattern=r"\d{2}/\d{2}/\d{4}")
    download_type: Literal["xml", "pdf", "both"] = "xml"
    force_update: bool = Field(False, description="Se true, atualiza notas já existentes re-extraindo do XML armazenado (sem baixar novamente da ADN)")
