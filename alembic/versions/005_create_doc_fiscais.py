from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_create_doc_fiscais"
down_revision = "004_add_auditoria_analise_fields"
branch_labels = None
depends_on = None


def upgrade():
    # Tabela documentos_fiscais
    op.create_table(
        "documentos_fiscais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("tipo_documento", sa.Enum("pgdas_d", "iss", "das", "folha_pagamento", "defis", "dirf", "efd_reinf", name="tipodocumento"), nullable=False),
        sa.Column("periodo", sa.String(7), nullable=False),
        sa.Column("ano_calendario", sa.Integer(), nullable=True),
        sa.Column("data_emissao", sa.DateTime(), nullable=True),
        sa.Column("data_vencimento", sa.DateTime(), nullable=True),
        sa.Column("data_pagamento", sa.DateTime(), nullable=True),
        sa.Column("numero_documento", sa.String(50), nullable=True),
        sa.Column("serie", sa.String(10), nullable=True),
        sa.Column("chave_acesso", sa.String(44), nullable=True),
        sa.Column("situacao", sa.String(20), nullable=True),
        sa.Column("valor_total", sa.Float(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("arquivo_fonte", sa.String(500), nullable=True),
        sa.Column("data_extracao", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ativo", sa.Boolean(), default=True),
    )
    op.create_index("ix_documentos_fiscais_id", "documentos_fiscais", ["id"])
    op.create_index("ix_documentos_fiscais_empresa_id", "documentos_fiscais", ["empresa_id"])
    op.create_index("ix_documentos_fiscais_tipo_documento", "documentos_fiscais", ["tipo_documento"])
    op.create_index("ix_documentos_fiscais_periodo", "documentos_fiscais", ["periodo"])

    # Tabela pgdas_d
    op.create_table(
        "pgdas_d",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("razao_social", sa.String(255)),
        sa.Column("periodo_apuracao", sa.String(7), nullable=False),
        sa.Column("regime_apuracao", sa.String(20)),
        sa.Column("receita_bruta_total", sa.Float()),
        sa.Column("receita_competencia", sa.Float()),
        sa.Column("receita_caixa", sa.Float()),
        sa.Column("receita_mercado_interno", sa.Float()),
        sa.Column("receita_mercado_externo", sa.Float()),
        sa.Column("rbt12", sa.Float()),
        sa.Column("rbt12_interno", sa.Float()),
        sa.Column("rbt12_externo", sa.Float()),
        sa.Column("valor_irpj", sa.Float()),
        sa.Column("valor_csll", sa.Float()),
        sa.Column("valor_pis", sa.Float()),
        sa.Column("valor_cofins", sa.Float()),
        sa.Column("valor_ipi", sa.Float()),
        sa.Column("valor_icms", sa.Float()),
        sa.Column("valor_iss", sa.Float()),
        sa.Column("valor_cpp", sa.Float()),
        sa.Column("valor_total_das", sa.Float()),
        sa.Column("anexo", sa.String(5)),
        sa.Column("faixa", sa.Integer()),
        sa.Column("aliquota_nominal", sa.Float()),
        sa.Column("aliquota_efetiva", sa.Float()),
        sa.Column("parcela_deduzir", sa.Float()),
        sa.Column("fator_r", sa.Float()),
        sa.Column("folha_12m", sa.Float()),
        sa.Column("receita_substituicao_tributaria", sa.Float()),
        sa.Column("receita_monofasica", sa.Float()),
        sa.Column("iss_retido", sa.Float()),
        sa.Column("icms_st", sa.Float()),
        sa.Column("difal", sa.Float()),
        sa.Column("data_transmissao", sa.DateTime()),
        sa.Column("recibo_transmissao", sa.String(50)),
        sa.Column("nfse_ids", sa.Text()),
    )
    op.create_index("ix_pgdas_d_id", "pgdas_d", ["id"])
    op.create_index("ix_pgdas_d_documento_fiscal_id", "pgdas_d", ["documento_fiscal_id"])

    # Tabela iss
    op.create_table(
        "iss",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("numero_documento", sa.String(18)),
        sa.Column("serie", sa.String(10)),
        sa.Column("data_emissao", sa.DateTime()),
        sa.Column("competencia", sa.String(7)),
        sa.Column("situacao", sa.String(20)),
        sa.Column("cnpj_prestador", sa.String(14)),
        sa.Column("razao_social_prestador", sa.String(255)),
        sa.Column("inscricao_municipal_prestador", sa.String(7)),
        sa.Column("cnpj_tomador", sa.String(14)),
        sa.Column("razao_social_tomador", sa.String(255)),
        sa.Column("inscricao_municipal_tomador", sa.String(7)),
        sa.Column("codigo_servico_lc116", sa.String(5)),
        sa.Column("descricao_servico", sa.Text()),
        sa.Column("cnae", sa.String(9)),
        sa.Column("natureza_operacao", sa.String(10)),
        sa.Column("valor_servico", sa.Float()),
        sa.Column("valor_deductions", sa.Float()),
        sa.Column("valor_descontos_incondicionados", sa.Float()),
        sa.Column("valor_descontos_condicionados", sa.Float()),
        sa.Column("base_calculo_iss", sa.Float()),
        sa.Column("aliquota_iss", sa.Float()),
        sa.Column("valor_iss", sa.Float()),
        sa.Column("valor_liquido", sa.Float()),
        sa.Column("indicador_iss_retido", sa.String(1)),
        sa.Column("valor_ir", sa.Float()),
        sa.Column("valor_pis", sa.Float()),
        sa.Column("valor_cofins", sa.Float()),
        sa.Column("valor_csll", sa.Float()),
        sa.Column("valor_inss", sa.Float()),
        sa.Column("data_pagamento", sa.DateTime()),
    )
    op.create_index("ix_iss_id", "iss", ["id"])
    op.create_index("ix_iss_documento_fiscal_id", "iss", ["documento_fiscal_id"])

    # Tabela das
    op.create_table(
        "das",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("numero_das", sa.String(50)),
        sa.Column("cnpj", sa.String(14)),
        sa.Column("periodo_apuracao", sa.String(7)),
        sa.Column("data_geracao", sa.DateTime()),
        sa.Column("data_vencimento", sa.DateTime()),
        sa.Column("data_pagamento", sa.DateTime()),
        sa.Column("rpa_total", sa.Float()),
        sa.Column("rpa_mercado_interno", sa.Float()),
        sa.Column("rpa_mercado_externo", sa.Float()),
        sa.Column("rbt12", sa.Float()),
        sa.Column("valor_irpj", sa.Float()),
        sa.Column("valor_csll", sa.Float()),
        sa.Column("valor_pis", sa.Float()),
        sa.Column("valor_cofins", sa.Float()),
        sa.Column("valor_ipi", sa.Float()),
        sa.Column("valor_icms", sa.Float()),
        sa.Column("valor_iss", sa.Float()),
        sa.Column("valor_cpp", sa.Float()),
        sa.Column("valor_total_das", sa.Float()),
        sa.Column("anexo", sa.String(5)),
        sa.Column("faixa", sa.Integer()),
        sa.Column("aliquota_nominal", sa.Float()),
        sa.Column("aliquota_efetiva", sa.Float()),
        sa.Column("parcela_deduzir", sa.Float()),
        sa.Column("fator_r", sa.Float()),
        sa.Column("fs12", sa.Float()),
        sa.Column("regime_apuracao", sa.String(20)),
        sa.Column("receita_substituicao_tributaria", sa.Float()),
        sa.Column("receita_monofasica", sa.Float()),
        sa.Column("iss_retido", sa.Float()),
        sa.Column("icms_st", sa.Float()),
        sa.Column("difal", sa.Float()),
    )
    op.create_index("ix_das_id", "das", ["id"])
    op.create_index("ix_das_documento_fiscal_id", "das", ["documento_fiscal_id"])

    # Tabela folha_pagamento
    op.create_table(
        "folha_pagamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("cnpj", sa.String(14)),
        sa.Column("razao_social", sa.String(255)),
        sa.Column("periodo_referencia", sa.String(7)),
        sa.Column("data_emissao", sa.DateTime()),
        sa.Column("total_salarios", sa.Float()),
        sa.Column("total_proventos", sa.Float()),
        sa.Column("total_descontos", sa.Float()),
        sa.Column("total_liquido", sa.Float()),
        sa.Column("base_inss", sa.Float()),
        sa.Column("aliquota_inss_empregado", sa.Float()),
        sa.Column("valor_inss_empregado", sa.Float()),
        sa.Column("aliquota_inss_patronal", sa.Float()),
        sa.Column("valor_inss_patronal", sa.Float()),
        sa.Column("base_fgts", sa.Float()),
        sa.Column("aliquota_fgts", sa.Float()),
        sa.Column("valor_fgts", sa.Float()),
        sa.Column("base_irrf", sa.Float()),
        sa.Column("valor_irrf", sa.Float()),
        sa.Column("base_pis", sa.Float()),
        sa.Column("valor_pis", sa.Float()),
        sa.Column("fs12", sa.Float()),
        sa.Column("rbt12", sa.Float()),
        sa.Column("fator_r", sa.Float()),
        sa.Column("quantidade_empregados", sa.Integer()),
    )
    op.create_index("ix_folha_pagamento_id", "folha_pagamento", ["id"])
    op.create_index("ix_folha_pagamento_documento_fiscal_id", "folha_pagamento", ["documento_fiscal_id"])

    # Tabela defis
    op.create_table(
        "defis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("cnpj", sa.String(14)),
        sa.Column("razao_social", sa.String(255)),
        sa.Column("ano_calendario", sa.Integer(), nullable=False),
        sa.Column("periodo_inicio", sa.DateTime()),
        sa.Column("periodo_fim", sa.DateTime()),
        sa.Column("empresa_inativa", sa.String(1)),
        sa.Column("receita_bruta_total", sa.Float()),
        sa.Column("receita_bruta_servicos", sa.Float()),
        sa.Column("receita_bruta_comercio", sa.Float()),
        sa.Column("receita_bruta_industria", sa.Float()),
        sa.Column("ganhos_capital", sa.Float()),
        sa.Column("ganhos_financeiros", sa.Float()),
        sa.Column("total_despesas", sa.Float()),
        sa.Column("despesas_operacionais", sa.Float()),
        sa.Column("despesas_pessoal", sa.Float()),
        sa.Column("estoque_inicial", sa.Float()),
        sa.Column("estoque_final", sa.Float()),
        sa.Column("saldo_caixa_inicial", sa.Float()),
        sa.Column("saldo_caixa_final", sa.Float()),
        sa.Column("saldo_banco_inicial", sa.Float()),
        sa.Column("saldo_banco_final", sa.Float()),
        sa.Column("quantidade_empregados_inicio", sa.Integer()),
        sa.Column("quantidade_empregados_final", sa.Integer()),
        sa.Column("valor_das", sa.Float()),
        sa.Column("iss_retido", sa.Float()),
        sa.Column("fgts", sa.Float()),
        sa.Column("data_entrega", sa.DateTime()),
        sa.Column("recibo", sa.String(50)),
    )
    op.create_index("ix_defis_id", "defis", ["id"])
    op.create_index("ix_defis_documento_fiscal_id", "defis", ["documento_fiscal_id"])

    # Tabela dirf
    op.create_table(
        "dirf",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("cnpj_declarante", sa.String(14)),
        sa.Column("razao_social_declarante", sa.String(255)),
        sa.Column("ano_calendario", sa.Integer(), nullable=False),
        sa.Column("cpf_beneficiario", sa.String(11)),
        sa.Column("cnpj_beneficiario", sa.String(14)),
        sa.Column("nome_beneficiario", sa.String(255)),
        sa.Column("tipo_beneficiario", sa.String(10)),
        sa.Column("codigo_receita", sa.String(4)),
        sa.Column("tipo_rendimento", sa.String(20)),
        sa.Column("descricao_rendimento", sa.Text()),
        sa.Column("valor_bruto", sa.Float()),
        sa.Column("base_calculo", sa.Float()),
        sa.Column("aliquota", sa.Float()),
        sa.Column("valor_retido", sa.Float()),
        sa.Column("mes_referencia", sa.Integer()),
        sa.Column("irrf", sa.Float()),
        sa.Column("csll", sa.Float()),
        sa.Column("cofins", sa.Float()),
        sa.Column("pis", sa.Float()),
        sa.Column("inss", sa.Float()),
        sa.Column("data_entrega", sa.DateTime()),
    )
    op.create_index("ix_dirf_id", "dirf", ["id"])
    op.create_index("ix_dirf_documento_fiscal_id", "dirf", ["documento_fiscal_id"])

    # Tabela efd_reinf
    op.create_table(
        "efd_reinf",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), unique=True),
        sa.Column("cnpj_contribuinte", sa.String(14)),
        sa.Column("periodo_apuracao", sa.String(7)),
        sa.Column("data_envio", sa.DateTime()),
        sa.Column("evento", sa.String(10)),
        sa.Column("cnpj_prestador", sa.String(14)),
        sa.Column("cnpj_tomador", sa.String(14)),
        sa.Column("serie", sa.String(10)),
        sa.Column("num_documento", sa.String(18)),
        sa.Column("data_emissao_documento", sa.DateTime()),
        sa.Column("valor_bruto", sa.Float()),
        sa.Column("valor_base_retencao", sa.Float()),
        sa.Column("valor_retencao", sa.Float()),
        sa.Column("valor_irrf", sa.Float()),
        sa.Column("valor_csll", sa.Float()),
        sa.Column("valor_cofins", sa.Float()),
        sa.Column("valor_pis", sa.Float()),
        sa.Column("valor_inss", sa.Float()),
        sa.Column("fechamento", sa.String(1)),
    )
    op.create_index("ix_efd_reinf_id", "efd_reinf", ["id"])
    op.create_index("ix_efd_reinf_documento_fiscal_id", "efd_reinf", ["documento_fiscal_id"])

    # Tabela documento_pendencias
    op.create_table(
        "documento_pendencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), nullable=False),
        sa.Column("tipo_documento", sa.String(100)),
        sa.Column("gravidade", sa.String(10)),
        sa.Column("status", sa.String(20)),
        sa.Column("observacao", sa.Text()),
        sa.Column("crf", sa.Float()),
        sa.Column("crt", sa.String(50)),
        sa.Column("base_calculo", sa.Float()),
        sa.Column("receita_declarada", sa.Float()),
        sa.Column("data_identificacao", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("data_resolucao", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documento_pendencias_id", "documento_pendencias", ["id"])
    op.create_index("ix_documento_pendencias_documento_fiscal_id", "documento_pendencias", ["documento_fiscal_id"])


def downgrade():
    op.drop_index("ix_documento_pendencias_documento_fiscal_id", table_name="documento_pendencias")
    op.drop_index("ix_documento_pendencias_id", table_name="documento_pendencias")
    op.drop_table("documento_pendencias")

    op.drop_index("ix_efd_reinf_documento_fiscal_id", table_name="efd_reinf")
    op.drop_index("ix_efd_reinf_id", table_name="efd_reinf")
    op.drop_table("efd_reinf")

    op.drop_index("ix_dirf_documento_fiscal_id", table_name="dirf")
    op.drop_index("ix_dirf_id", table_name="dirf")
    op.drop_table("dirf")

    op.drop_index("ix_defis_documento_fiscal_id", table_name="defis")
    op.drop_index("ix_defis_id", table_name="defis")
    op.drop_table("defis")

    op.drop_index("ix_folha_pagamento_documento_fiscal_id", table_name="folha_pagamento")
    op.drop_index("ix_folha_pagamento_id", table_name="folha_pagamento")
    op.drop_table("folha_pagamento")

    op.drop_index("ix_das_documento_fiscal_id", table_name="das")
    op.drop_index("ix_das_id", table_name="das")
    op.drop_table("das")

    op.drop_index("ix_iss_documento_fiscal_id", table_name="iss")
    op.drop_index("ix_iss_id", table_name="iss")
    op.drop_table("iss")

    op.drop_index("ix_pgdas_d_documento_fiscal_id", table_name="pgdas_d")
    op.drop_index("ix_pgdas_d_id", table_name="pgdas_d")
    op.drop_table("pgdas_d")

    op.drop_index("ix_documentos_fiscais_periodo", table_name="documentos_fiscais")
    op.drop_index("ix_documentos_fiscais_tipo_documento", table_name="documentos_fiscais")
    op.drop_index("ix_documentos_fiscais_empresa_id", table_name="documentos_fiscais")
    op.drop_index("ix_documentos_fiscais_id", table_name="documentos_fiscais")
    op.drop_table("documentos_fiscais")

    op.execute("DROP TYPE IF EXISTS tipodocumento")
