from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class EfdReinfBase(BaseModel):
    documento_fiscal_id: int
    cnpj_contribuinte: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    data_envio: Optional[datetime] = None
    evento: Optional[str] = None
    cnpj_prestador: Optional[str] = None
    cnpj_tomador: Optional[str] = None
    serie: Optional[str] = None
    num_documento: Optional[str] = None
    data_emissao_documento: Optional[datetime] = None
    valor_bruto: Optional[float] = None
    valor_base_retencao: Optional[float] = None
    valor_retencao: Optional[float] = None
    valor_irrf: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_inss: Optional[float] = None
    fechamento: Optional[str] = None


class EfdReinfCreate(EfdReinfBase):
    pass


class EfdReinfUpdate(BaseModel):
    cnpj_contribuinte: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    data_envio: Optional[datetime] = None
    evento: Optional[str] = None
    cnpj_prestador: Optional[str] = None
    cnpj_tomador: Optional[str] = None
    serie: Optional[str] = None
    num_documento: Optional[str] = None
    data_emissao_documento: Optional[datetime] = None
    valor_bruto: Optional[float] = None
    valor_base_retencao: Optional[float] = None
    valor_retencao: Optional[float] = None
    valor_irrf: Optional[float] = None
    valor_csll: Optional[float] = None
    valor_cofins: Optional[float] = None
    valor_pis: Optional[float] = None
    valor_inss: Optional[float] = None
    fechamento: Optional[str] = None


class EfdReinfOut(EfdReinfBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
