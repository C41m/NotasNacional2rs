from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TipoDocumento(str, Enum):
    PGDAS_D = "pgdas_d"
    ISS = "iss"
    DAS = "das"
    FOLHA_PAGAMENTO = "folha_pagamento"
    DEFIS = "defis"
    DIRF = "dirf"
    EFD_REINF = "efd_reinf"


class DocumentoFiscalBase(BaseModel):
    empresa_id: int = Field(..., gt=0)
    tipo_documento: TipoDocumento
    periodo: str = Field(..., max_length=7, pattern=r"^\d{4}-\d{2}$")
    ano_calendario: Optional[int] = None
    data_emissao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    data_pagamento: Optional[datetime] = None
    numero_documento: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=10)
    chave_acesso: Optional[str] = Field(None, max_length=44)
    situacao: Optional[str] = Field(None, max_length=20)
    valor_total: Optional[float] = None
    observacao: Optional[str] = None
    arquivo_fonte: Optional[str] = Field(None, max_length=500)
    ativo: bool = True


class DocumentoFiscalCreate(DocumentoFiscalBase):
    pass


class DocumentoFiscalUpdate(BaseModel):
    tipo_documento: Optional[TipoDocumento] = None
    periodo: Optional[str] = Field(None, max_length=7, pattern=r"^\d{4}-\d{2}$")
    ano_calendario: Optional[int] = None
    data_emissao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    data_pagamento: Optional[datetime] = None
    numero_documento: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=10)
    chave_acesso: Optional[str] = Field(None, max_length=44)
    situacao: Optional[str] = Field(None, max_length=20)
    valor_total: Optional[float] = None
    observacao: Optional[str] = None
    arquivo_fonte: Optional[str] = Field(None, max_length=500)
    ativo: Optional[bool] = None


class DocumentoFiscalOut(DocumentoFiscalBase):
    id: int
    data_extracao: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentoFiscalResumoOut(BaseModel):
    id: int
    empresa_id: int
    tipo_documento: TipoDocumento
    periodo: str
    ano_calendario: Optional[int] = None
    data_emissao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    numero_documento: Optional[str] = None
    situacao: Optional[str] = None
    valor_total: Optional[float] = None
    ativo: bool

    model_config = ConfigDict(from_attributes=True)
