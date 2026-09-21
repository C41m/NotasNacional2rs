from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class FolhaPagamento(Base):
    __tablename__ = "folha_pagamento"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    cnpj = Column(String(14))
    razao_social = Column(String(255))
    periodo_referencia = Column(String(7))  # MM/AAAA
    data_emissao = Column(DateTime)

    # Remuneração
    total_salarios = Column(Float)
    total_proventos = Column(Float)
    total_descontos = Column(Float)
    total_liquido = Column(Float)

    # INSS
    base_inss = Column(Float)
    aliquota_inss_empregado = Column(Float)
    valor_inss_empregado = Column(Float)
    aliquota_inss_patronal = Column(Float)
    valor_inss_patronal = Column(Float)

    # FGTS
    base_fgts = Column(Float)
    aliquota_fgts = Column(Float)
    valor_fgts = Column(Float)

    # IRRF
    base_irrf = Column(Float)
    valor_irrf = Column(Float)

    # PIS
    base_pis = Column(Float)
    valor_pis = Column(Float)

    # Fator R
    fs12 = Column(Float)  # Folha acumulada 12 meses
    rbt12 = Column(Float)
    fator_r = Column(Float)

    # Empregados
    quantidade_empregados = Column(Integer)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="folha_pagamento")
