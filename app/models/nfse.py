from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Nfse(Base):
    __tablename__ = "nfse"

    id = Column(Integer, primary_key=True, index=True)
    documento_fiscal_id = Column(
        Integer, ForeignKey("documentos_fiscais.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Identificação da NFS-e (NFSe/infNFSe/)
    identificador_nfse = Column(String(53), nullable=True)      # atributo id do infNFSe
    numero_nfse = Column(String(13), nullable=True)             # nNFSe
    codigo_verificacao = Column(String(50), nullable=True)      # código de verificação
    versao_leiaute = Column(String(10), nullable=True)          # versao
    data_emissao = Column(DateTime, nullable=True)              # dhEmi
    competencia = Column(String(7), nullable=True)              # dCompet / dhEmi (YYYY-MM)
    municipio_emissor_codigo = Column(String(7), nullable=True) # cLocEmi / cMun
    municipio_emissor_descricao = Column(String(150), nullable=True)  # xLocEmi
    local_prestacao = Column(String(150), nullable=True)        # xLocPrestacao
    local_incidencia_codigo = Column(String(7), nullable=True)  # cLocIncid
    local_incidencia_descricao = Column(String(150), nullable=True)  # xLocIncida
    tributo_nacional = Column(Text, nullable=True)              # xTribNac
    tributo_municipal = Column(Text, nullable=True)             # xTribMun
    codigo_nbs = Column(String(20), nullable=True)              # xNBS
    versao_aplicacao = Column(String(50), nullable=True)        # verAplic
    ambiente_gerador = Column(String(1), nullable=True)         # ambGer
    tipo_emissao = Column(String(1), nullable=True)             # tpEmis
    processo_emissao = Column(String(1), nullable=True)         # procEmi
    codigo_status = Column(String(10), nullable=True)           # cStat
    data_processamento = Column(DateTime, nullable=True)        # dhProc
    numero_dfse = Column(String(20), nullable=True)             # nDFSe

    # Prestador (NFSe/infNFSe/prest/ ou emit/)
    cnpj_prestador = Column(String(14), nullable=True)
    cpf_prestador = Column(String(11), nullable=True)
    razao_social_prestador = Column(String(255), nullable=True)  # xNome
    inscricao_municipal_prestador = Column(String(20), nullable=True)  # IM
    caepf_prestador = Column(String(20), nullable=True)
    nif_prestador = Column(String(40), nullable=True)
    cnao_nif_prestador = Column(String(1), nullable=True)
    # Endereço do prestador (enderNac)
    prest_logradouro = Column(String(200), nullable=True)   # xLgr
    prest_numero = Column(String(20), nullable=True)        # nro
    prest_bairro = Column(String(100), nullable=True)       # xBairro
    prest_codigo_municipio = Column(String(7), nullable=True)  # cMun
    prest_uf = Column(String(2), nullable=True)             # UF
    prest_cep = Column(String(8), nullable=True)            # CEP
    prest_telefone = Column(String(20), nullable=True)      # fone
    prest_email = Column(String(255), nullable=True)        # email

    # Tomador (NFSe/infNFSe/toma/)
    cnpj_tomador = Column(String(14), nullable=True)
    cpf_tomador = Column(String(11), nullable=True)
    razao_social_tomador = Column(String(255), nullable=True)    # xNome
    inscricao_municipal_tomador = Column(String(20), nullable=True)  # IM
    caepf_tomador = Column(String(20), nullable=True)
    nif_tomador = Column(String(40), nullable=True)
    cnao_nif_tomador = Column(String(1), nullable=True)

    # Serviço (NFSe/infNFSe/serv/)
    codigo_servico = Column(String(20), nullable=True)           # cServ
    descricao_servico = Column(Text, nullable=True)
    informacoes_complementares = Column(Text, nullable=True)     # serv/infoCompl/xInfComp
    numero_pedido = Column(String(60), nullable=True)            # serv/infoCompl/xPed

    # Valores (NFSe/infNFSe/valores/)
    valor_servico = Column(Float, nullable=True)                 # vServPrest/vServ
    valor_recebido = Column(Float, nullable=True)                # vServPrest/vReceb
    valor_desconto_condicionado = Column(Float, nullable=True)   # vDescCondIncond/vDescCond
    valor_desconto_incondicionado = Column(Float, nullable=True) # vDescCondIncond/vDescIncond
    valor_liquido = Column(Float, nullable=True)                 # valor líquido da nota
    base_calculo_iss = Column(Float, nullable=True)
    aliquota_iss = Column(Float, nullable=True)
    valor_iss = Column(Float, nullable=True)                     # vISSQN
    iss_retido = Column(String(1), nullable=True)                # tpRetISSQN (0-Não, 1-Sim)
    valor_iss_retido = Column(Float, nullable=True)              # vRetISSQN
    # Valores adicionais (valores/)
    base_calculo_valor = Column(Float, nullable=True)            # vBC
    aliquota_aplicada = Column(Float, nullable=True)             # pAliqAplic
    valor_total_retencoes = Column(Float, nullable=True)         # vTotalRet
    valor_liquido_calculado = Column(Float, nullable=True)       # vLiq

    # Retenções federais (valores/trib/tribFed/)
    valor_retido_cp = Column(Float, nullable=True)               # vRetCP
    valor_retido_irrf = Column(Float, nullable=True)             # vRetIRRF
    valor_retido_csll = Column(Float, nullable=True)             # vRetCSLL
    valor_retido_pis = Column(Float, nullable=True)              # vRetPis
    valor_retido_cofins = Column(Float, nullable=True)           # vRetCofins

    # Chaves de referência
    chave_acesso = Column(String(60), nullable=True)             # chNFSe / chave da NFS-e
    chave_nfe_referenciada = Column(String(60), nullable=True)   # chaveDFe / chNFe

    # Evento (pedRegEvento/infPedReg)
    tipo_evento = Column(String(10), nullable=True)              # tpEvento
    descricao_evento = Column(String(100), nullable=True)        # xMotivo / descrição do evento
    data_evento = Column(DateTime, nullable=True)                # dhEvento / dhRegEvento

    # Controle de integração ADN
    nsu = Column(Integer, nullable=True)                         # NSU da distribuição ADN
    tipo_documento_api = Column(String(20), nullable=True)       # NFSE / EVENTO / DPS
    role = Column(String(20), nullable=True)                     # prestado / tomado / intermediario
    xml_original = Column(Text, nullable=True)                   # XML completo bruto
    arquivo_fonte = Column(String(500), nullable=True)           # caminho do arquivo origem

    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())

    documento_fiscal = relationship("DocumentoFiscal", back_populates="nfse", uselist=False)
