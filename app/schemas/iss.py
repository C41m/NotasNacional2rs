from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class IssBase(BaseModel):
    documento_fiscal_id: int
    numero_documento: Optional[str] = None
    serie: Optional[str] = None
    data_emissao: Optional[datetime] = None
    competencia: Optional[str] = None
    situacao: Optional[str] = None
    cnpj_prestador: Optional[str] = None
    razao_social_prestador: Optional[str] = None
    inscricao_municipal_prestador: Optional[str] = None
    cnpj_tomador: Optional[str] = None
    razao_social_tomador: Optional[str] = None
    inscricao_municipal_tomador: Optional[str] = None
    codigo_servico_lc116: Optional[str] = None
    descricao_servico: Optional[str] = None
    cnae: Optional[str] = None
    natureza_operacao: Optional[str] = None
    valor_servico: Optional[float] = None
    valor_deductions: Optional[float] = None
    valor_descontos_incondicionados: Optional[float] = None
    valor_descontos_condicionados: Optional[float] = None
    base_calculo_iss: Optional[float] = None
    aliquota_iss: Optional[float] = None
    valor_iss: Optional[float] = None
    valor_liquido: Optional[float] = None
    indicador_iss_retido: Optional[str] = None
    valor_ir: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_inss: Optional[float] = None
    data_pagamento: Optional[datetime] = None


class IssCreate(IssBase):
    pass


class IssUpdate(BaseModel):
    numero_documento: Optional[str] = None
    serie: Optional[str] = None
    data_emissao: Optional[datetime] = None
    competencia: Optional[str] = None
    situacao: Optional[str] = None
    cnpj_prestador: Optional[str] = None
    razao_social_prestador: Optional[str] = None
    inscricao_municipal_prestador: Optional[str] = None
    cnpj_tomador: Optional[str] = None
    razao_social_tomador: Optional[str] = None
    inscricao_municipal_tomador: Optional[str] = None
    codigo_servico_lc116: Optional[str] = None
    descricao_servico: Optional[str] = None
    cnae: Optional[str] = None
    natureza_operacao: Optional[str] = None
    valor_servico: Optional[float] = None
    valor_deductions: Optional[float] = None
    valor_descontos_incondicionados: Optional[float] = None
    valor_descontos_condicionados: Optional[float] = None
    base_calculo_iss: Optional[float] = None
    aliquota_iss: Optional[float] = None
    valor_iss: Optional[float] = None
    valor_liquido: Optional[float] = None
    indicador_iss_retido: Optional[str] = None
    valor_ir: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_inss: Optional[float] = None
    data_pagamento: Optional[datetime] = None


class IssOut(IssBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
