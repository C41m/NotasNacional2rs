from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class DocumentoPendenciaBase(BaseModel):
    documento_fiscal_id: int
    tipo_documento: Optional[str] = None
    gravidade: Optional[str] = None
    status: Optional[str] = None
    observacao: Optional[str] = None
    crf: Optional[float] = None
    crt: Optional[str] = None
    base_calculo: Optional[float] = None
    receita_declarada: Optional[float] = None
    data_resolucao: Optional[datetime] = None


class DocumentoPendenciaCreate(DocumentoPendenciaBase):
    pass


class DocumentoPendenciaUpdate(BaseModel):
    tipo_documento: Optional[str] = None
    gravidade: Optional[str] = None
    status: Optional[str] = None
    observacao: Optional[str] = None
    crf: Optional[float] = None
    crt: Optional[str] = None
    base_calculo: Optional[float] = None
    receita_declarada: Optional[float] = None
    data_resolucao: Optional[datetime] = None


class DocumentoPendenciaOut(DocumentoPendenciaBase):
    id: int
    data_identificacao: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
