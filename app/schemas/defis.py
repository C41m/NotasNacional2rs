from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class DefisBase(BaseModel):
    documento_fiscal_id: int
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    ano_calendario: int
    periodo_inicio: Optional[datetime] = None
    periodo_fim: Optional[datetime] = None
    empresa_inativa: Optional[str] = None
    receita_bruta_total: Optional[float] = None
    receita_bruta_servicos: Optional[float] = None
    receita_bruta_comercio: Optional[float] = None
    receita_bruta_industria: Optional[float] = None
    ganhos_capital: Optional[float] = None
    ganhos_financeiros: Optional[float] = None
    total_despesas: Optional[float] = None
    despesas_operacionais: Optional[float] = None
    despesas_pessoal: Optional[float] = None
    estoque_inicial: Optional[float] = None
    estoque_final: Optional[float] = None
    saldo_caixa_inicial: Optional[float] = None
    saldo_caixa_final: Optional[float] = None
    saldo_banco_inicial: Optional[float] = None
    saldo_banco_final: Optional[float] = None
    quantidade_empregados_inicio: Optional[int] = None
    quantidade_empregados_final: Optional[int] = None
    valor_das: Optional[float] = None
    iss_retido: Optional[float] = None
    fgts: Optional[float] = None
    data_entrega: Optional[datetime] = None
    recibo: Optional[str] = None


class DefisCreate(DefisBase):
    pass


class DefisUpdate(BaseModel):
    cnpj: Optional[str] = None
    razao_social: Optional[str] = None
    ano_calendario: Optional[int] = None
    periodo_inicio: Optional[datetime] = None
    periodo_fim: Optional[datetime] = None
    empresa_inativa: Optional[str] = None
    receita_bruta_total: Optional[float] = None
    receita_bruta_servicos: Optional[float] = None
    receita_bruta_comercio: Optional[float] = None
    receita_bruta_industria: Optional[float] = None
    ganhos_capital: Optional[float] = None
    ganhos_financeiros: Optional[float] = None
    total_despesas: Optional[float] = None
    despesas_operacionais: Optional[float] = None
    despesas_pessoal: Optional[float] = None
    estoque_inicial: Optional[float] = None
    estoque_final: Optional[float] = None
    saldo_caixa_inicial: Optional[float] = None
    saldo_caixa_final: Optional[float] = None
    saldo_banco_inicial: Optional[float] = None
    saldo_banco_final: Optional[float] = None
    quantidade_empregados_inicio: Optional[int] = None
    quantidade_empregados_final: Optional[int] = None
    valor_das: Optional[float] = None
    iss_retido: Optional[float] = None
    fgts: Optional[float] = None
    data_entrega: Optional[datetime] = None
    recibo: Optional[str] = None


class DefisOut(DefisBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
