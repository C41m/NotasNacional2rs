from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Das(Base):
    __tablename__ = "das"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    numero_das = Column(String(50))
    cnpj = Column(String(14))
    periodo_apuracao = Column(String(7))

    # Datas
    data_geracao = Column(DateTime)
    data_vencimento = Column(DateTime)
    data_pagamento = Column(DateTime)

    # Receita
    rpa_total = Column(Float)
    rpa_mercado_interno = Column(Float)
    rpa_mercado_externo = Column(Float)
    rbt12 = Column(Float)

    # Tributos
    valor_irpj = Column(Float)
    valor_csll = Column(Float)
    valor_pis = Column(Float)
    valor_cofins = Column(Float)
    valor_ipi = Column(Float)
    valor_icms = Column(Float)
    valor_iss = Column(Float)
    valor_cpp = Column(Float)
    valor_total_das = Column(Float)

    # Cálculo
    anexo = Column(String(5))
    faixa = Column(Integer)
    aliquota_nominal = Column(Float)
    aliquota_efetiva = Column(Float)
    parcela_deduzir = Column(Float)
    fator_r = Column(Float)
    fs12 = Column(Float)
    regime_apuracao = Column(String(20))

    # Ajustes
    receita_substituicao_tributaria = Column(Float)
    receita_monofasica = Column(Float)
    iss_retido = Column(Float)
    icms_st = Column(Float)
    difal = Column(Float)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="das")
