from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Defis(Base):
    __tablename__ = "defis"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(Integer, ForeignKey("documentos_fiscais.id"), unique=True)

    # Identificação
    cnpj = Column(String(14))
    razao_social = Column(String(255))
    ano_calendario = Column(Integer, nullable=False)

    # Período
    periodo_inicio = Column(DateTime)
    periodo_fim = Column(DateTime)
    empresa_inativa = Column(String(1))  # S/N

    # Receitas
    receita_bruta_total = Column(Float)
    receita_bruta_servicos = Column(Float)
    receita_bruta_comercio = Column(Float)
    receita_bruta_industria = Column(Float)
    ganhos_capital = Column(Float)
    ganhos_financeiros = Column(Float)

    # Despesas
    total_despesas = Column(Float)
    despesas_operacionais = Column(Float)
    despesas_pessoal = Column(Float)

    # Estoque
    estoque_inicial = Column(Float)
    estoque_final = Column(Float)

    # Patrimônio
    saldo_caixa_inicial = Column(Float)
    saldo_caixa_final = Column(Float)
    saldo_banco_inicial = Column(Float)
    saldo_banco_final = Column(Float)

    # Empregados
    quantidade_empregados_inicio = Column(Integer)
    quantidade_empregados_final = Column(Integer)

    # Tributos
    valor_das = Column(Float)
    iss_retido = Column(Float)
    fgts = Column(Float)

    # Entrega
    data_entrega = Column(DateTime)
    recibo = Column(String(50))

    documento_fiscal = relationship("DocumentoFiscal", back_populates="defis")
