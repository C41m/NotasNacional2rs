"""add xml_hash to nfse for delta detection

Revision ID: add_xml_hash_nfse
Revises: 
Create Date: 2024-11-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_add_xml_hash_nfse'
down_revision = '008_add_missing_nfse_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add xml_hash column to nfse table
    op.add_column('nfse', sa.Column('xml_hash', sa.String(32), nullable=True))


def downgrade() -> None:
    # Remove xml_hash column
    op.drop_column('nfse', 'xml_hash')