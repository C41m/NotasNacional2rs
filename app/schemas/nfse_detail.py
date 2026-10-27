from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class NfseBase(BaseModel):
    identificador_nfse: Optional[str] = Field(None, max_length=53)
    numero_nfse: Optional[str] = Field(None, max_length=13)
    codigo_verificacao: Optional[str] = Field(None, max_length=50)
    versao_leiaute: Optional[str] = Field(None, max_length=10)
    data_emissao: Optional[datetime] = None
    competencia: Optional[str] = Field(None, max_length=7, pattern=r"^\d{4}-\d{2}$")
    municipio_emissor_codigo: Optional[str] = Field(None, max_length=7)
    municipio_emissor_descricao: Optional[str] = Field(None, max_length=150)
    local_prestacao: Optional[str] = Field(None, max_length=150)            # xLocPrestacao
    local_incidencia_codigo: Optional[str] = Field(None, max_length=7)      # cLocIncid
    local_incidencia_descricao: Optional[str] = Field(None, max_length=150) # xLocIncida
    tributo_nacional: Optional[str] = None                                  # xTribNac
    tributo_municipal: Optional[str] = None                                 # xTribMun
    codigo_nbs: Optional[str] = Field(None, max_length=20)                  # xNBS
    versao_aplicacao: Optional[str] = Field(None, max_length=50)            # verAplic
    ambiente_gerador: Optional[str] = Field(None, max_length=1)             # ambGer
    tipo_emissao: Optional[str] = Field(None, max_length=1)                 # tpEmis
    processo_emissao: Optional[str] = Field(None, max_length=1)             # procEmi
    codigo_status: Optional[str] = Field(None, max_length=10)               # cStat
    data_processamento: Optional[datetime] = None                           # dhProc
    numero_dfse: Optional[str] = Field(None, max_length=20)                 # nDFSe

    # Prestador
    cnpj_prestador: Optional[str] = Field(None, max_length=14)
    cpf_prestador: Optional[str] = Field(None, max_length=11)
    razao_social_prestador: Optional[str] = Field(None, max_length=255)
    inscricao_municipal_prestador: Optional[str] = Field(None, max_length=20)
    caepf_prestador: Optional[str] = Field(None, max_length=20)
    nif_prestador: Optional[str] = Field(None, max_length=40)
    cnao_nif_prestador: Optional[str] = Field(None, max_length=1)
    # Endereço do prestador (enderNac)
    prest_logradouro: Optional[str] = Field(None, max_length=200)   # xLgr
    prest_numero: Optional[str] = Field(None, max_length=20)        # nro
    prest_bairro: Optional[str] = Field(None, max_length=100)       # xBairro
    prest_codigo_municipio: Optional[str] = Field(None, max_length=7)   # cMun
    prest_uf: Optional[str] = Field(None, max_length=2)             # UF
    prest_cep: Optional[str] = Field(None, max_length=8)            # CEP
    prest_telefone: Optional[str] = Field(None, max_length=20)      # fone
    prest_email: Optional[str] = Field(None, max_length=255)        # email

    # Tomador
    cnpj_tomador: Optional[str] = Field(None, max_length=14)
    cpf_tomador: Optional[str] = Field(None, max_length=11)
    razao_social_tomador: Optional[str] = Field(None, max_length=255)
    inscricao_municipal_tomador: Optional[str] = Field(None, max_length=20)
    caepf_tomador: Optional[str] = Field(None, max_length=20)
    nif_tomador: Optional[str] = Field(None, max_length=40)
    cnao_nif_tomador: Optional[str] = Field(None, max_length=1)

    # Serviço
    codigo_servico: Optional[str] = Field(None, max_length=20)
    descricao_servico: Optional[str] = None
    informacoes_complementares: Optional[str] = None
    numero_pedido: Optional[str] = Field(None, max_length=60)

    # Valores
    valor_servico: Optional[float] = None
    valor_recebido: Optional[float] = None
    valor_desconto_condicionado: Optional[float] = None
    valor_desconto_incondicionado: Optional[float] = None
    valor_liquido: Optional[float] = None
    base_calculo_iss: Optional[float] = None
    aliquota_iss: Optional[float] = None
    valor_iss: Optional[float] = None
    iss_retido: Optional[str] = Field(None, max_length=1)
    valor_iss_retido: Optional[float] = None
    # Valores adicionais (valores/)
    base_calculo_valor: Optional[float] = None      # vBC
    aliquota_aplicada: Optional[float] = None       # pAliqAplic
    valor_total_retencoes: Optional[float] = None   # vTotalRet
    valor_liquido_calculado: Optional[float] = None # vLiq

    # Retenções federais
    valor_retido_cp: Optional[float] = None
    valor_retido_irrf: Optional[float] = None
    valor_retido_csll: Optional[float] = None
    valor_retido_pis: Optional[float] = None
    valor_retido_cofins: Optional[float] = None

    # Chaves de referência
    chave_acesso: Optional[str] = Field(None, max_length=60)
    chave_nfe_referenciada: Optional[str] = Field(None, max_length=60)

    # Evento
    tipo_evento: Optional[str] = Field(None, max_length=10)
    descricao_evento: Optional[str] = Field(None, max_length=100)
    data_evento: Optional[datetime] = None

    # Controle de integração ADN
    nsu: Optional[int] = None
    tipo_documento_api: Optional[str] = Field(None, max_length=20)
    role: Optional[str] = Field(None, max_length=20)
    xml_original: Optional[str] = None
    arquivo_fonte: Optional[str] = Field(None, max_length=500)


class NfseCreate(NfseBase):
    documento_fiscal_id: int = Field(..., gt=0)


class NfseOut(NfseBase):
    id: int
    documento_fiscal_id: int
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Schemas para persistência de NFSe baixada via ADN
# ---------------------------------------------------------------------------

class NfseSalvarItem(BaseModel):
    nsu: Optional[int] = None
    tipo_documento_api: Optional[str] = None
    role: Optional[str] = None
    chave: Optional[str] = None
    competencia: Optional[str] = Field(None, max_length=7, pattern=r"^\d{4}-\d{2}$")
    xml: str


class NfseSalvarRequest(BaseModel):
    empresa_id: int = Field(..., gt=0)
    xmls: List[NfseSalvarItem] = Field(..., min_length=1)

