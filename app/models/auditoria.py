from sqlalchemy import Column, Float, Integer, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Auditoria(Base):
    __tablename__ = "auditorias"

    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String(14), nullable=False, index=True)
    razao_social = Column(String(255))
    periodo = Column(String(7), nullable=False, index=True)
    status_geral = Column(String(20))
    conformidade_pct = Column(Float)
    observacao_geral = Column(Text, nullable=True)
    documentos_esperados = Column(Integer)
    documentos_encontrados = Column(Integer)
    # Novos campos para análise IA (Fator R, alíquotas, etc.)
    fator_r = Column(Float)
    aliquota_efetiva = Column(Float)
    receita_pa = Column(Float)
    rbt12 = Column(Float)
    folha_12m = Column(Float)
    pro_labore = Column(Float)
    inss = Column(Float)
    irrf = Column(Float)
    fgts = Column(Float)
    num_funcionarios = Column(Integer)
    media_mensal_folha = Column(Float)
    classificacao_anexo = Column(String(50))
    analise_completa = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    pendencias = relationship(
        "AuditoriaPendencia",
        back_populates="auditoria",
        cascade="all, delete-orphan",
    )


class AuditoriaPendencia(Base):
    __tablename__ = "auditoria_pendencias"

    id = Column(Integer, primary_key=True, index=True)
    auditoria_id = Column(
        Integer, ForeignKey("auditorias.id", ondelete="CASCADE"), nullable=False
    )
    tipo_documento = Column(String(100))
    gravidade = Column(String(10))
    status = Column(String(20))
    observacao = Column(Text)
    # Novos campos para análise IA
    crf = Column(Float)
    crt = Column(String(50))
    base_calculo = Column(Float)
    receita_declarada = Column(Float)

    auditoria = relationship("Auditoria", back_populates="pendencias")
