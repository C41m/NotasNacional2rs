from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean, func
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum


class TipoDocumento(enum.Enum):
    PGDAS_D = "pgdas_d"
    ISS = "iss"
    DAS = "das"
    FOLHA_PAGAMENTO = "folha_pagamento"
    DEFIS = "defis"
    DIRF = "dirf"
    EFD_REINF = "efd_reinf"


class DocumentoFiscal(Base):
    __tablename__ = "documentos_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    tipo_documento = Column(Enum(TipoDocumento, values_callable=lambda x: [e.value for e in x]), nullable=False)
    periodo = Column(String(7), nullable=False)  # YYYY-MM
    ano_calendario = Column(Integer, nullable=True)  # Para DEFIS/DIRF
    data_emissao = Column(DateTime, nullable=True)
    data_vencimento = Column(DateTime, nullable=True)
    data_pagamento = Column(DateTime, nullable=True)
    numero_documento = Column(String(50), nullable=True)
    serie = Column(String(10), nullable=True)
    chave_acesso = Column(String(44), nullable=True)
    situacao = Column(String(20), nullable=True)
    valor_total = Column(Float, nullable=True)
    observacao = Column(Text, nullable=True)
    arquivo_fonte = Column(String(500), nullable=True)  # Caminho do PDF/XML
    data_extracao = Column(DateTime, server_default=func.now())
    ativo = Column(Boolean, default=True)

    empresa = relationship("Company", back_populates="documentos_fiscais")
    pgdas_d = relationship("PgdasD", back_populates="documento_fiscal", uselist=False)
    iss = relationship("Iss", back_populates="documento_fiscal", uselist=False)
    das = relationship("Das", back_populates="documento_fiscal", uselist=False)
    folha_pagamento = relationship("FolhaPagamento", back_populates="documento_fiscal", uselist=False)
    defis = relationship("Defis", back_populates="documento_fiscal", uselist=False)
    dirf = relationship("Dirf", back_populates="documento_fiscal", uselist=False)
    efd_reinf = relationship("EfdReinf", back_populates="documento_fiscal", uselist=False)
    pendencias = relationship("DocumentoPendencia", back_populates="documento_fiscal", cascade="all, delete-orphan")
