from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class DasBase(BaseModel):
    documento_fiscal_id: int
    numero_das: Optional[str] = None
    cnpj: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    data_geracao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    data_pagamento: Optional[datetime] = None
    rpa_total: Optional[float] = None
    rpa_mercado_interno: Optional[float] = None
    rpa_mercado_externo: Optional[float] = None
    rbt12: Optional[float] = None
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
    fs12: Optional[float] = None
    regime_apuracao: Optional[str] = None
    receita_substituicao_tributaria: Optional[float] = None
    receita_monofasica: Optional[float] = None
    iss_retido: Optional[float] = None
    icms_st: Optional[float] = None
    difal: Optional[float] = None


class DasCreate(DasBase):
    pass


class DasUpdate(BaseModel):
    numero_das: Optional[str] = None
    cnpj: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    data_geracao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    data_pagamento: Optional[datetime] = None
    rpa_total: Optional[float] = None
    rpa_mercado_interno: Optional[float] = None
    rpa_mercado_externo: Optional[float] = None
    rbt12: Optional[float] = None
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
    fs12: Optional[float] = None
    regime_apuracao: Optional[str] = None
    receita_substituicao_tributaria: Optional[float] = None
    receita_monofasica: Optional[float] = None
    iss_retido: Optional[float] = None
    icms_st: Optional[float] = None
    difal: Optional[float] = None


class DasOut(DasBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
