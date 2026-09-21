from pydantic import BaseModel, ConfigDict
from typing import Optional


class AuditoriaStats(BaseModel):
    total_auditorias: int
    conformes: int
    atencao: int
    criticos: int
    conformidade_media: float
    total_pendencias: int
    pendencias_faltantes: int
    pendencias_inconsistentes: int

    model_config = ConfigDict(from_attributes=True)


class CompanyStats(BaseModel):
    total_companies: int
    companies_ativas: int
    companies_com_auditoria: int
    companies_sem_auditoria: int

    model_config = ConfigDict(from_attributes=True)


class DownloadJobStats(BaseModel):
    total_jobs: int
    jobs_queued: int
    jobs_processing: int
    jobs_success: int
    jobs_failed: int
    total_registros_processados: int

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    auditoria: AuditoriaStats
    company: CompanyStats
    download_job: DownloadJobStats

    model_config = ConfigDict(from_attributes=True)
