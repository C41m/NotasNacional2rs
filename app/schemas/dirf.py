from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class DirfBase(BaseModel):
    documento_fiscal_id: int
    cnpj_declarante: Optional[str] = None
    razao_social_declarante: Optional[str] = None
    ano_calendario: int
    cpf_beneficiario: Optional[str] = None
    cnpj_beneficiario: Optional[str] = None
    nome_beneficiario: Optional[str] = None
    tipo_beneficiario: Optional[str] = None
    codigo_receita: Optional[str] = None
    tipo_rendimento: Optional[str] = None
    descricao_rendimento: Optional[str] = None
    valor_bruto: Optional[float] = None
    base_calculo: Optional[float] = None
    aliquota: Optional[float] = None
    valor_retido: Optional[float] = None
    mes_referencia: Optional[int] = None
    irrf: Optional[float] = None
    csll: Optional[float] = None
    cofins: Optional[float] = None
    pis: Optional[float] = None
    inss: Optional[float] = None
    data_entrega: Optional[datetime] = None


class DirfCreate(DirfBase):
    pass


class DirfUpdate(BaseModel):
    cnpj_declarante: Optional[str] = None
    razao_social_declarante: Optional[str] = None
    ano_calendario: Optional[int] = None
    cpf_beneficiario: Optional[str] = None
    cnpj_beneficiario: Optional[str] = None
    nome_beneficiario: Optional[str] = None
    tipo_beneficiario: Optional[str] = None
    codigo_receita: Optional[str] = None
    tipo_rendimento: Optional[str] = None
    descricao_rendimento: Optional[str] = None
    valor_bruto: Optional[float] = None
    base_calculo: Optional[float] = None
    aliquota: Optional[float] = None
    valor_retido: Optional[float] = None
    mes_referencia: Optional[int] = None
    irrf: Optional[float] = None
    csll: Optional[float] = None
    cofins: Optional[float] = None
    pis: Optional[float] = None
    inss: Optional[float] = None
    data_entrega: Optional[datetime] = None


class DirfOut(DirfBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
