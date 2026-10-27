"""Add missing NFSe fields from leiaute SPED

Revision ID: 008_add_missing_nfse_fields
Revises: 007_alter_chave_acesso_size
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "008_add_missing_nfse_fields"
down_revision = "007_alter_chave_acesso_size"
branch_labels = None
depends_on = None


def upgrade():
    # Identificação administrativa
    op.add_column("nfse", sa.Column("local_prestacao", sa.String(150), nullable=True))
    op.add_column("nfse", sa.Column("local_incidencia_codigo", sa.String(7), nullable=True))
    op.add_column("nfse", sa.Column("local_incidencia_descricao", sa.String(150), nullable=True))
    op.add_column("nfse", sa.Column("tributo_nacional", sa.Text(), nullable=True))
    op.add_column("nfse", sa.Column("tributo_municipal", sa.Text(), nullable=True))
    op.add_column("nfse", sa.Column("codigo_nbs", sa.String(20), nullable=True))
    op.add_column("nfse", sa.Column("versao_aplicacao", sa.String(50), nullable=True))
    op.add_column("nfse", sa.Column("ambiente_gerador", sa.String(1), nullable=True))
    op.add_column("nfse", sa.Column("tipo_emissao", sa.String(1), nullable=True))
    op.add_column("nfse", sa.Column("processo_emissao", sa.String(1), nullable=True))
    op.add_column("nfse", sa.Column("codigo_status", sa.String(10), nullable=True))
    op.add_column("nfse", sa.Column("data_processamento", sa.DateTime(), nullable=True))
    op.add_column("nfse", sa.Column("numero_dfse", sa.String(20), nullable=True))

    # Endereço do prestador
    op.add_column("nfse", sa.Column("prest_logradouro", sa.String(200), nullable=True))
    op.add_column("nfse", sa.Column("prest_numero", sa.String(20), nullable=True))
    op.add_column("nfse", sa.Column("prest_bairro", sa.String(100), nullable=True))
    op.add_column("nfse", sa.Column("prest_codigo_municipio", sa.String(7), nullable=True))
    op.add_column("nfse", sa.Column("prest_uf", sa.String(2), nullable=True))
    op.add_column("nfse", sa.Column("prest_cep", sa.String(8), nullable=True))
    op.add_column("nfse", sa.Column("prest_telefone", sa.String(20), nullable=True))
    op.add_column("nfse", sa.Column("prest_email", sa.String(255), nullable=True))

    # Valores adicionais
    op.add_column("nfse", sa.Column("base_calculo_valor", sa.Float(), nullable=True))
    op.add_column("nfse", sa.Column("aliquota_aplicada", sa.Float(), nullable=True))
    op.add_column("nfse", sa.Column("valor_total_retencoes", sa.Float(), nullable=True))
    op.add_column("nfse", sa.Column("valor_liquido_calculado", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("nfse", "prest_email")
    op.drop_column("nfse", "prest_telefone")
    op.drop_column("nfse", "prest_cep")
    op.drop_column("nfse", "prest_uf")
    op.drop_column("nfse", "prest_codigo_municipio")
    op.drop_column("nfse", "prest_bairro")
    op.drop_column("nfse", "prest_numero")
    op.drop_column("nfse", "prest_logradouro")
    op.drop_column("nfse", "valor_liquido_calculado")
    op.drop_column("nfse", "valor_total_retencoes")
    op.drop_column("nfse", "aliquota_aplicada")
    op.drop_column("nfse", "base_calculo_valor")
    op.drop_column("nfse", "numero_dfse")
    op.drop_column("nfse", "data_processamento")
    op.drop_column("nfse", "codigo_status")
    op.drop_column("nfse", "processo_emissao")
    op.drop_column("nfse", "tipo_emissao")
    op.drop_column("nfse", "ambiente_gerador")
    op.drop_column("nfse", "versao_aplicacao")
    op.drop_column("nfse", "codigo_nbs")
    op.drop_column("nfse", "tributo_municipal")
    op.drop_column("nfse", "tributo_nacional")
    op.drop_column("nfse", "local_incidencia_descricao")
    op.drop_column("nfse", "local_incidencia_codigo")
    op.drop_column("nfse", "local_prestacao")
