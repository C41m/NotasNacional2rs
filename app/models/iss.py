from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Iss(Base):
    __tablename__ = "iss"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    numero_documento = Column(String(18))
    serie = Column(String(10))
    data_emissao = Column(DateTime)
    competencia = Column(String(7))  # MM/AAAA
    situacao = Column(String(20))  # Normal, Cancelado

    # Prestador
    cnpj_prestador = Column(String(14))
    razao_social_prestador = Column(String(255))
    inscricao_municipal_prestador = Column(String(7))

    # Tomador
    cnpj_tomador = Column(String(14))
    razao_social_tomador = Column(String(255))
    inscricao_municipal_tomador = Column(String(7))

    # Serviço
    codigo_servico_lc116 = Column(String(5))
    descricao_servico = Column(Text)
    cnae = Column(String(9))
    natureza_operacao = Column(String(10))

    # Valores
    valor_servico = Column(Float)
    valor_deductions = Column(Float)
    valor_descontos_incondicionados = Column(Float)
    valor_descontos_condicionados = Column(Float)
    base_calculo_iss = Column(Float)
    aliquota_iss = Column(Float)
    valor_iss = Column(Float)
    valor_liquido = Column(Float)

    # Retenções
    indicador_iss_retido = Column(String(1))  # 0-Não, 1-Sim
    valor_ir = Column(Float)
    valor_pis = Column(Float)
    valor_cofins = Column(Float)
    valor_csll = Column(Float)
    valor_inss = Column(Float)

    # Pagamento
    data_pagamento = Column(DateTime)

    documento_fiscal = relationship("DocumentoFiscal", back_populates="iss")
