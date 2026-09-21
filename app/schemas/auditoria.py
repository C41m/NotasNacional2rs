from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class StatusGeral(str, Enum):
    CONFORME = "CONFORME"
    ATENCAO = "ATENCAO"
    CRITICO = "CRITICO"


class Gravidade(str, Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class StatusPendencia(str, Enum):
    FALTANTE = "FALTANTE"
    INCONSISTENTE = "INCONSISTENTE"


class AuditoriaPendenciaIngest(BaseModel):
    tipo_documento: str
    gravidade: str
    status: str
    observacao: Optional[str] = None
    crf: Optional[float] = None
    crt: Optional[str] = None
    base_calculo: Optional[float] = None
    receita_declarada: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AuditoriaIngestRequest(BaseModel):
    cnpj: str = Field(..., max_length=14)
    razao_social: str = Field(..., max_length=255)
    periodo: str = Field(..., max_length=7)
    status_geral: StatusGeral
    conformidade_pct: float = Field(..., ge=0.0, le=100.0)
    observacao_geral: Optional[str] = None
    documentos_esperados: int
    documentos_encontrados: int
    # Novos campos para análise IA
    fator_r: float = 0.0
    aliquota_efetiva: float = 0.0
    receita_pa: float = 0.0
    rbt12: float = 0.0
    folha_12m: float = 0.0
    pro_labore: Optional[float] = None
    inss: Optional[float] = None
    irrf: Optional[float] = None
    fgts: Optional[float] = None
    num_funcionarios: Optional[int] = None
    media_mensal_folha: Optional[float] = None
    classificacao_anexo: Optional[str] = None
    analise_completa: Optional[str] = None
    pendencias: List[AuditoriaPendenciaIngest]

    model_config = ConfigDict(from_attributes=True)


class AuditoriaPendenciaOut(BaseModel):
    id: int
    auditoria_id: int
    tipo_documento: str
    gravidade: str
    status: str
    observacao: Optional[str] = None
    crf: Optional[float] = None
    crt: Optional[str] = None
    base_calculo: Optional[float] = None
    receita_declarada: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AuditoriaOut(BaseModel):
    id: int
    cnpj: str
    razao_social: str
    periodo: str
    status_geral: str
    conformidade_pct: float
    observacao_geral: Optional[str] = None
    documentos_esperados: int
    documentos_encontrados: int
    # Novos campos para análise IA (opcionais para backward compatibility)
    fator_r: Optional[float] = None
    aliquota_efetiva: Optional[float] = None
    receita_pa: Optional[float] = None
    rbt12: Optional[float] = None
    folha_12m: Optional[float] = None
    pro_labore: Optional[float] = None
    inss: Optional[float] = None
    irrf: Optional[float] = None
    fgts: Optional[float] = None
    num_funcionarios: Optional[int] = None
    media_mensal_folha: Optional[float] = None
    classificacao_anexo: Optional[str] = None
    analise_completa: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pendencias: List[AuditoriaPendenciaOut] = []

    model_config = ConfigDict(from_attributes=True)


class AuditoriaResumoOut(BaseModel):
    id: int
    cnpj: str
    razao_social: str
    periodo: str
    status_geral: str
    conformidade_pct: float
    fator_r: Optional[float] = None
    aliquota_efetiva: Optional[float] = None
    classificacao_anexo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
