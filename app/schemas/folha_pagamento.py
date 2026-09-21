from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class FolhaPagamentoBase(BaseModel):
    documento_fiscal_id: int
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    periodo_referencia: Optional[str] = None
    data_emissao: Optional[datetime] = None
    total_salarios: Optional[float] = None
    total_proventos: Optional[float] = None
    total_descontos: Optional[float] = None
    total_liquido: Optional[float] = None
    base_inss: Optional[float] = None
    aliquota_inss_empregado: Optional[float] = None
    valor_inss_empregado: Optional[float] = None
    aliquota_inss_patronal: Optional[float] = None
    valor_inss_patronal: Optional[float] = None
    base_fgts: Optional[float] = None
    aliquota_fgts: Optional[float] = None
    valor_fgts: Optional[float] = None
    base_irrf: Optional[float] = None
    valor_irrf: Optional[float] = None
    base_pis: Optional[float] = None
    valor_pis: Optional[float] = None
    fs12: Optional[float] = None
    rbt12: Optional[float] = None
    fator_r: Optional[float] = None
    quantidade_empregados: Optional[int] = None


class FolhaPagamentoCreate(FolhaPagamentoBase):
    pass


class FolhaPagamentoUpdate(BaseModel):
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    periodo_referencia: Optional[str] = None
    data_emissao: Optional[datetime] = None
    total_salarios: Optional[float] = None
    total_proventos: Optional[float] = None
    total_descontos: Optional[float] = None
    total_liquido: Optional[float] = None
    base_inss: Optional[float] = None
    aliquota_inss_empregado: Optional[float] = None
    valor_inss_empregado: Optional[float] = None
    aliquota_inss_patronal: Optional[float] = None
    valor_inss_patronal: Optional[float] = None
    base_fgts: Optional[float] = None
    aliquota_fgts: Optional[float] = None
    valor_fgts: Optional[float] = None
    base_irrf: Optional[float] = None
    valor_irrf: Optional[float] = None
    base_pis: Optional[float] = None
    valor_pis: Optional[float] = None
    fs12: Optional[float] = None
    rbt12: Optional[float] = None
    fator_r: Optional[float] = None
    quantidade_empregados: Optional[int] = None


class FolhaPagamentoOut(FolhaPagamentoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
