from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class EfdReinf(Base):
    __tablename__ = "efd_reinf"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    cnpj_contribuinte = Column(String(14))
    periodo_apuracao = Column(String(7))  # MM/AAAA
    data_envio = Column(DateTime)

    # Evento
    evento = Column(String(10))  # R-1000, R-2010, R-2020, R-2060, R-4010, R-4020, R-2099, R-4099

    # Dados do evento
    cnpj_prestador = Column(String(14))
    cnpj_tomador = Column(String(14))
    serie = Column(String(10))
    num_documento = Column(String(18))
    data_emissao_documento = Column(DateTime)

    # Valores
    valor_bruto = Column(Float)
    valor_base_retencao = Column(Float)
    valor_retencao = Column(Float)

    # Retenções
    valor_irrf = Column(Float)
    valor_csll = Column(Float)
    valor_cofins = Column(Float)
    valor_pis = Column(Float)
    valor_inss = Column(Float)

    # Fechamento
    fechamento = Column(String(1))  # S/N (R-2099/R-4099)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="efd_reinf")
