"""Increase chave_acesso size from 44 to 60

Revision ID: 007_alter_chave_acesso_size
Revises: 006_create_nfse_table
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "007_alter_chave_acesso_size"
down_revision = "006_create_nfse_table"
branch_labels = None
depends_on = None


def upgrade():
    # documentos_fiscais.chave_acesso
    op.alter_column(
        "documentos_fiscais",
        "chave_acesso",
        existing_type=sa.String(44),
        type_=sa.String(60),
        existing_nullable=True,
    )
    # nfse.chave_acesso
    op.alter_column(
        "nfse",
        "chave_acesso",
        existing_type=sa.String(44),
        type_=sa.String(60),
        existing_nullable=True,
    )
    # nfse.chave_nfe_referenciada
    op.alter_column(
        "nfse",
        "chave_nfe_referenciada",
        existing_type=sa.String(44),
        type_=sa.String(60),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "nfse",
        "chave_nfe_referenciada",
        existing_type=sa.String(60),
        type_=sa.String(44),
        existing_nullable=True,
    )
    op.alter_column(
        "nfse",
        "chave_acesso",
        existing_type=sa.String(60),
        type_=sa.String(44),
        existing_nullable=True,
    )
    op.alter_column(
        "documentos_fiscais",
        "chave_acesso",
        existing_type=sa.String(60),
        type_=sa.String(44),
        existing_nullable=True,
    )
