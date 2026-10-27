"""Create tabela nfse

Revision ID: 006_create_nfse_table
Revises: 005_create_doc_fiscais
Create Date: 2026-10-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006_create_nfse_table"
down_revision = "005_create_doc_fiscais"
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar 'nfse' ao enum tipodocumento existente (PostgreSQL ALTER TYPE)
    op.execute("ALTER TYPE tipodocumento ADD VALUE 'nfse'")

    # Tabela nfse (detalhe da nota fiscal de serviço eletrônica nacional)
    op.create_table(
        "nfse",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "documento_fiscal_id",
            sa.Integer(),
            sa.ForeignKey("documentos_fiscais.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        # Identificação da NFS-e (NFSe/infNFSe/)
        sa.Column("identificador_nfse", sa.String(53), nullable=True),
        sa.Column("numero_nfse", sa.String(13), nullable=True),
        sa.Column("codigo_verificacao", sa.String(50), nullable=True),
        sa.Column("versao_leiaute", sa.String(10), nullable=True),
        sa.Column("data_emissao", sa.DateTime(), nullable=True),
        sa.Column("competencia", sa.String(7), nullable=True),
        sa.Column("municipio_emissor_codigo", sa.String(7), nullable=True),
        sa.Column("municipio_emissor_descricao", sa.String(150), nullable=True),
        # Prestador (NFSe/infNFSe/prest/ ou emit/)
        sa.Column("cnpj_prestador", sa.String(14), nullable=True),
        sa.Column("cpf_prestador", sa.String(11), nullable=True),
        sa.Column("razao_social_prestador", sa.String(255), nullable=True),
        sa.Column("inscricao_municipal_prestador", sa.String(20), nullable=True),
        sa.Column("caepf_prestador", sa.String(20), nullable=True),
        sa.Column("nif_prestador", sa.String(40), nullable=True),
        sa.Column("cnao_nif_prestador", sa.String(1), nullable=True),
        # Tomador (NFSe/infNFSe/toma/)
        sa.Column("cnpj_tomador", sa.String(14), nullable=True),
        sa.Column("cpf_tomador", sa.String(11), nullable=True),
        sa.Column("razao_social_tomador", sa.String(255), nullable=True),
        sa.Column("inscricao_municipal_tomador", sa.String(20), nullable=True),
        sa.Column("caepf_tomador", sa.String(20), nullable=True),
        sa.Column("nif_tomador", sa.String(40), nullable=True),
        sa.Column("cnao_nif_tomador", sa.String(1), nullable=True),
        # Serviço (NFSe/infNFSe/serv/)
        sa.Column("codigo_servico", sa.String(20), nullable=True),
        sa.Column("descricao_servico", sa.Text(), nullable=True),
        sa.Column("informacoes_complementares", sa.Text(), nullable=True),
        sa.Column("numero_pedido", sa.String(60), nullable=True),
        # Valores (NFSe/infNFSe/valores/)
        sa.Column("valor_servico", sa.Float(), nullable=True),
        sa.Column("valor_recebido", sa.Float(), nullable=True),
        sa.Column("valor_desconto_condicionado", sa.Float(), nullable=True),
        sa.Column("valor_desconto_incondicionado", sa.Float(), nullable=True),
        sa.Column("valor_liquido", sa.Float(), nullable=True),
        sa.Column("base_calculo_iss", sa.Float(), nullable=True),
        sa.Column("aliquota_iss", sa.Float(), nullable=True),
        sa.Column("valor_iss", sa.Float(), nullable=True),
        sa.Column("iss_retido", sa.String(1), nullable=True),
        sa.Column("valor_iss_retido", sa.Float(), nullable=True),
        # Retenções federais (valores/trib/tribFed/)
        sa.Column("valor_retido_cp", sa.Float(), nullable=True),
        sa.Column("valor_retido_irrf", sa.Float(), nullable=True),
        sa.Column("valor_retido_csll", sa.Float(), nullable=True),
        sa.Column("valor_retido_pis", sa.Float(), nullable=True),
        sa.Column("valor_retido_cofins", sa.Float(), nullable=True),
        # Chaves de referência
        sa.Column("chave_acesso", sa.String(44), nullable=True),
        sa.Column("chave_nfe_referenciada", sa.String(44), nullable=True),
        # Evento (pedRegEvento/infPedReg)
        sa.Column("tipo_evento", sa.String(10), nullable=True),
        sa.Column("descricao_evento", sa.String(100), nullable=True),
        sa.Column("data_evento", sa.DateTime(), nullable=True),
        # Controle de integração ADN
        sa.Column("nsu", sa.Integer(), nullable=True),
        sa.Column("tipo_documento_api", sa.String(20), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("xml_original", sa.Text(), nullable=True),
        sa.Column("arquivo_fonte", sa.String(500), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_nfse_id", "nfse", ["id"])
    op.create_index("ix_nfse_documento_fiscal_id", "nfse", ["documento_fiscal_id"])
    op.create_index("ix_nfse_chave_acesso", "nfse", ["chave_acesso"])
    op.create_index("ix_nfse_nsu", "nfse", ["nsu"])
    op.create_index("ix_nfse_competencia", "nfse", ["competencia"])


def downgrade():
    op.drop_index("ix_nfse_competencia", table_name="nfse")
    op.drop_index("ix_nfse_nsu", table_name="nfse")
    op.drop_index("ix_nfse_chave_acesso", table_name="nfse")
    op.drop_index("ix_nfse_documento_fiscal_id", table_name="nfse")
    op.drop_index("ix_nfse_id", table_name="nfse")
    op.drop_table("nfse")
    # Nota: PostgreSQL não suporta DROP VALUE de enum nativamente.
    # O valor 'nfse' permanece no tipo tipodocumento após downgrade.
