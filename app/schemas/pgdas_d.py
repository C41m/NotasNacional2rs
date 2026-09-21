from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class PgdasDBase(BaseModel):
    documento_fiscal_id: int
    cnpj: str
    razao_social: Optional[str] = None
    periodo_apuracao: str
    regime_apuracao: Optional[str] = None
    receita_bruta_total: Optional[float] = None
    receita_competencia: Optional[float] = None
    receita_caixa: Optional[float] = None
    receita_mercado_interno: Optional[float] = None
    receita_mercado_externo: Optional[float] = None
    rbt12: Optional[float] = None
    rbt12_interno: Optional[float] = None
    rbt12_externo: Optional[float] = None
    valor_irpj: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_ipi: Optional[float] = None
    valor_icms: Optional[float] = None
    valor_iss: Optional[float] = None
    valor_cpp: Optional[float] = None
    valor_total_das: Optional[float] = None
    anexo: Optional[str] = None
    faixa: Optional[int] = None
    aliquota_nominal: Optional[float] = None
    aliquota_efetiva: Optional[float] = None
    parcela_deduzir: Optional[float] = None
    fator_r: Optional[float] = None
    folha_12m: Optional[float] = None
    receita_substituicao_tributaria: Optional[float] = None
    receita_monofasica: Optional[float] = None
    iss_retido: Optional[float] = None
    icms_st: Optional[float] = None
    difal: Optional[float] = None
    data_transmissao: Optional[datetime] = None
    recibo_transmissao: Optional[str] = None
    nfse_ids: Optional[str] = None


class PgdasDCreate(PgdasDBase):
    pass


class PgdasDUpdate(BaseModel):
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    regime_apuracao: Optional[str] = None
    receita_bruta_total: Optional[float] = None
    receita_competencia: Optional[float] = None
    receita_caixa: Optional[float] = None
    receita_mercado_interno: Optional[float] = None
    receita_mercado_externo: Optional[float] = None
    rbt12: Optional[float] = None
    rbt12_interno: Optional[float] = None
    rbt12_externo: Optional[float] = None
    valor_irpj: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_ipi: Optional[float] = None
    valor_icms: Optional[float] = None
    valor_iss: Optional[float] = None
    valor_cpp: Optional[float] = None
    valor_total_das: Optional[float] = None
    anexo: Optional[str] = None
    faixa: Optional[int] = None
    aliquota_nominal: Optional[float] = None
    aliquota_efetiva: Optional[float] = None
    parcela_deduzir: Optional[float] = None
    fator_r: Optional[float] = None
    folha_12m: Optional[float] = None
    receita_substituicao_tributaria: Optional[float] = None
    receita_monofasica: Optional[float] = None
    iss_retido: Optional[float] = None
    icms_st: Optional[float] = None
    difal: Optional[float] = None
    data_transmissao: Optional[datetime] = None
    recibo_transmissao: Optional[str] = None
    nfse_ids: Optional[str] = None


class PgdasDOut(PgdasDBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
