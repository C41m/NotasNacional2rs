from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class PgdasD(Base):
    __tablename__ = "pgdas_d"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    cnpj = Column(String(14), nullable=False)
    razao_social = Column(String(255))
    periodo_apuracao = Column(String(7), nullable=False)  # MM/AAAA

    # Regime
    regime_apuracao = Column(String(20))  # Competência / Caixa

    # Receitas
    receita_bruta_total = Column(Float)
    receita_competencia = Column(Float)
    receita_caixa = Column(Float)
    receita_mercado_interno = Column(Float)
    receita_mercado_externo = Column(Float)

    # RBT12
    rbt12 = Column(Float)
    rbt12_interno = Column(Float)
    rbt12_externo = Column(Float)

    # Tributos (8 componentes)
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
    anexo = Column(String(5))  # I, II, III, IV, V
    faixa = Column(Integer)
    aliquota_nominal = Column(Float)
    aliquota_efetiva = Column(Float)
    parcela_deduzir = Column(Float)

    # Fator R
    fator_r = Column(Float)
    folha_12m = Column(Float)

    # Qualificações tributárias
    receita_substituicao_tributaria = Column(Float)
    receita_monofasica = Column(Float)
    iss_retido = Column(Float)
    icms_st = Column(Float)
    difal = Column(Float)

    # Transmissão
    data_transmissao = Column(DateTime)
    recibo_transmissao = Column(String(50))

    # Cruzamento
    nfse_ids = Column(Text)  # IDs das NFSe relacionadas

    documento_fiscal = relationship("DocumentoFiscal", back_populates="pgdas_d")
