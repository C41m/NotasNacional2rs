from alembic import op
import sqlalchemy as sa

revision = "002_add_notas_processed"
down_revision = "001_initial_migration"

def upgrade():
    op.add_column("download_jobs", sa.Column("notas_processed", sa.Integer(), nullable=True, default=0))
    op.add_column("download_jobs", sa.Column("total_registros", sa.Integer(), nullable=True))
    op.add_column("download_jobs", sa.Column("data_inicio", sa.String(10), nullable=True))
    op.add_column("download_jobs", sa.Column("data_fim", sa.String(10), nullable=True))


def downgrade():
    op.drop_column("download_jobs", "data_fim")
    op.drop_column("download_jobs", "data_inicio")
    op.drop_column("download_jobs", "total_registros")
    op.drop_column("download_jobs", "notas_processed")
