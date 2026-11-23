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
    codigo_nbs: Optional[str] = None                                           # xNBS (descrição, sem limite)
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


class NotaResumoOut(BaseModel):
    id: int
    documento_fiscal_id: int
    empresa_id: int
    empresa_nome: Optional[str] = None
    empresa_cnpj: Optional[str] = None
    competencia: Optional[str] = None
    data_emissao: Optional[datetime] = None
    numero_nfse: Optional[str] = None
    chave_acesso: Optional[str] = None
    role: Optional[str] = None
    tipo_documento_api: Optional[str] = None
    tipo_evento: Optional[str] = None
    situacao: Optional[str] = None
    cnpj_prestador: Optional[str] = None
    razao_social_prestador: Optional[str] = None
    cnpj_tomador: Optional[str] = None
    razao_social_tomador: Optional[str] = None
    codigo_servico: Optional[str] = None
    descricao_servico: Optional[str] = None
    valor_servico: Optional[float] = None
    valor_liquido: Optional[float] = None
    base_calculo_iss: Optional[float] = None
    aliquota_iss: Optional[float] = None
    valor_iss: Optional[float] = None
    iss_retido: Optional[str] = None
    valor_iss_retido: Optional[float] = None
    valor_total: Optional[float] = None
    ativo: bool = True
    atualizado_em: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotaDetalheOut(NfseOut):
    empresa_id: Optional[int] = None
    empresa_nome: Optional[str] = None
    empresa_cnpj: Optional[str] = None
    situacao: Optional[str] = None
    valor_total: Optional[float] = None
    tem_xml: bool = False


class DashboardResumoOut(BaseModel):
    total_notas: int = 0
    total_valor_servico: float = 0
    total_iss: float = 0
    total_iss_retido: float = 0
    notas_prestadas: int = 0
    notas_tomadas: int = 0
    notas_outras: int = 0
    notas_canceladas: int = 0
    empresas_com_notas: int = 0
    notas_sem_competencia: int = 0
    notas_sem_xml: int = 0
    # Camada de verificação (cálculo automático, sem marcação manual)
    ultima_sincronizacao: Optional[datetime] = None
    notas_novas_desde_ontem: int = 0
    saude_conferencia: str = "ok"  # "ok" | "atencao"
    valor_prestado: float = 0
    valor_tomado: float = 0


class DashboardSerieItem(BaseModel):
    competencia: Optional[str] = None
    total_notas: int = 0
    notas_prestadas: int = 0
    notas_tomadas: int = 0
    valor_servico: float = 0
    valor_iss: float = 0
    valor_prestado: float = 0
    valor_tomado: float = 0


class DashboardEmpresaItem(BaseModel):
    empresa_id: int
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    total_notas: int = 0
    notas_prestadas: int = 0
    notas_tomadas: int = 0
    valor_servico: float = 0
    valor_iss: float = 0
    valor_prestado: float = 0
    valor_tomado: float = 0


# ---------------------------------------------------------------------------
# Análise por empresa (tela /analise/empresa)
# ---------------------------------------------------------------------------


class AnaliseAtividadeItem(BaseModel):
    atividade: str
    papel: Optional[str] = None  # prestado | tomado (linha do mix = atividade × papel)
    notas: int = 0
    valor: float = 0
    pct: float = 0
    # Desdobramento por papel (para a tabela separada)
    notas_prestadas: int = 0
    valor_prestado: float = 0
    notas_tomadas: int = 0
    valor_tomado: float = 0


class AnaliseMatrizItem(BaseModel):
    atividade: str
    cliente: Optional[str] = None
    cnpj: Optional[str] = None
    papel: Optional[str] = None  # prestado | tomado (lente usada na contraparte)
    notas: int = 0
    valor: float = 0
    pct: float = 0


class AnaliseClienteItem(BaseModel):
    cliente: Optional[str] = None
    cnpj: Optional[str] = None
    papel: Optional[str] = None  # prestado | tomado (papel da contraparte)
    notas: int = 0
    valor: float = 0
    pct: float = 0
    pct_acum: float = 0
    # Preenchido apenas na lista "Por quantidade" (pct_acum lá = % acumulado de NOTAS)
    pct_notas_acum: Optional[float] = None


class AnaliseEmpresaOut(BaseModel):
    empresa_nome: Optional[str] = None
    empresa_cnpj: Optional[str] = None
    role: Optional[str] = None
    competencia_inicio: Optional[str] = None
    competencia_fim: Optional[str] = None
    periodo_anterior: str = ""

    total_notas: int = 0
    notas_prestadas: int = 0
    notas_tomadas: int = 0
    valor_prestado: float = 0
    valor_tomado: float = 0
    clientes_unicos: int = 0
    ticket_medio: float = 0

    var_prestado_anterior: Optional[float] = None  # fração (0.12 = +12%)
    var_tomado_anterior: Optional[float] = None

    canceladas: int = 0
    sem_xml: int = 0
    sem_competencia: int = 0
    sem_papel: int = 0  # notas com papel outlier/indefinido (≠ prestado/tomado)

    # Retenções federais no período (prestadas + tomadas)
    valor_retido_cp: float = 0
    valor_retido_irrf: float = 0
    pct_retido_cp_irrf: Optional[float] = None  # % sobre o total de serviços

    # ISS retido (tpRetISSQN = 2 — retido pelo tomador)
    valor_iss_retido: float = 0
    notas_iss_retido: int = 0

    # Notas com valor de ISS calculado mas alíquota não informada (data quality)
    iss_sem_aliquota: int = 0

    # Curva A: quantos clientes concentram os primeiros 80% do faturamento
    clientes_curva_a: Optional[int] = None
    clientes_curva_a_pct_base: Optional[float] = None  # % desses clientes sobre a base única

    # Atividade dominante (top 1 do mix por R$)
    atividade_dominante: Optional[str] = None
    atividade_dominante_pct: Optional[float] = None

    serie: List[DashboardSerieItem] = []
    mix: List[AnaliseAtividadeItem] = []
    clientes: List[AnaliseClienteItem] = []
    clientes_por_notas: List[AnaliseClienteItem] = []
    matriz_prestadas: List[AnaliseMatrizItem] = []
    matriz_tomadas: List[AnaliseMatrizItem] = []


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

