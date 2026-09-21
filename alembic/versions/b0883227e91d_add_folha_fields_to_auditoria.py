"""add folha fields to auditoria

Revision ID: b0883227e91d
Revises: 005_create_doc_fiscais
Create Date: 2026-09-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0883227e91d'
down_revision = '005_create_doc_fiscais'
branch_labels = None
depends_on = None


def upgrade():
    # Add folha fields to auditorias table
    op.add_column('auditorias', sa.Column('pro_labore', sa.Float(), nullable=True))
    op.add_column('auditorias', sa.Column('inss', sa.Float(), nullable=True))
    op.add_column('auditorias', sa.Column('irrf', sa.Float(), nullable=True))
    op.add_column('auditorias', sa.Column('fgts', sa.Float(), nullable=True))
    op.add_column('auditorias', sa.Column('num_funcionarios', sa.Integer(), nullable=True))
    op.add_column('auditorias', sa.Column('media_mensal_folha', sa.Float(), nullable=True))


def downgrade():
    # Remove folha fields from auditorias table
    op.drop_column('auditorias', 'media_mensal_folha')
    op.drop_column('auditorias', 'num_funcionarios')
    op.drop_column('auditorias', 'fgts')
    op.drop_column('auditorias', 'irrf')
    op.drop_column('auditorias', 'inss')
    op.drop_column('auditorias', 'pro_labore')
