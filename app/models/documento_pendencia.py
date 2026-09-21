from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class DocumentoPendencia(Base):
    __tablename__ = "documento_pendencias"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), nullable=False)

    # Identificação da pendência
    tipo_documento = Column(String(100))
    gravidade = Column(String(10))  # ALTA, MEDIA, BAIXA
    status = Column(String(20))  # FALTANTE, PENDENTE, RESOLVIDO

    # Detalhes
    observacao = Column(Text)
    crf = Column(Float)
    crt = Column(String(50))
    base_calculo = Column(Float)
    receita_declarada = Column(Float)

    # Datas
    data_identificacao = Column(DateTime, server_default=func.now())
    data_resolucao = Column(DateTime, nullable=True)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="pendencias")
