from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Dirf(Base):
    __tablename__ = "dirf"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    cnpj_declarante = Column(String(14))
    razao_social_declarante = Column(String(255))
    ano_calendario = Column(Integer, nullable=False)

    # Beneficiário
    cpf_beneficiario = Column(String(11))
    cnpj_beneficiario = Column(String(14))
    nome_beneficiario = Column(String(255))
    tipo_beneficiario = Column(String(10))  # PF ou PJ

    # Rendimentos
    codigo_receita = Column(String(4))
    tipo_rendimento = Column(String(20))  # Tributável, Isento, Não tributável
    descricao_rendimento = Column(Text)
    valor_bruto = Column(Float)
    base_calculo = Column(Float)
    aliquota = Column(Float)
    valor_retido = Column(Float)
    mes_referencia = Column(Integer)

    # Impostos retidos
    irrf = Column(Float)
    csll = Column(Float)
    cofins = Column(Float)
    pis = Column(Float)
    inss = Column(Float)

    # Entrega
    data_entrega = Column(DateTime)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="dirf")
