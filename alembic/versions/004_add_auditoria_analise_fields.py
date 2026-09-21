from alembic import op
import sqlalchemy as sa

revision = "004_add_auditoria_analise_fields"
down_revision = "003_create_auditoria_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Fix: conformidade_pct was incorrectly created as VARCHAR(10) in 003
    # Correct it to FLOAT to match the model
    op.execute("ALTER TABLE auditorias ALTER COLUMN conformidade_pct TYPE FLOAT USING conformidade_pct::float")

    # Add new columns to auditorias
    op.add_column("auditorias", sa.Column("fator_r", sa.Float, nullable=True))
    op.add_column("auditorias", sa.Column("aliquota_efetiva", sa.Float, nullable=True))
    op.add_column("auditorias", sa.Column("receita_pa", sa.Float, nullable=True))
    op.add_column("auditorias", sa.Column("rbt12", sa.Float, nullable=True))
    op.add_column("auditorias", sa.Column("folha_12m", sa.Float, nullable=True))
    op.add_column("auditorias", sa.Column("classificacao_anexo", sa.String(50), nullable=True))
    op.add_column("auditorias", sa.Column("analise_completa", sa.Text, nullable=True))

    # Add new columns to auditoria_pendencias
    op.add_column("auditoria_pendencias", sa.Column("crf", sa.Float, nullable=True))
    op.add_column("auditoria_pendencias", sa.Column("crt", sa.String(50), nullable=True))
    op.add_column("auditoria_pendencias", sa.Column("base_calculo", sa.Float, nullable=True))
    op.add_column("auditoria_pendencias", sa.Column("receita_declarada", sa.Float, nullable=True))


def downgrade():
    # Remover colunas da tabela auditoria_pendencias
    op.drop_column("auditoria_pendencias", "receita_declarada")
    op.drop_column("auditoria_pendencias", "base_calculo")
    op.drop_column("auditoria_pendencias", "crt")
    op.drop_column("auditoria_pendencias", "crf")

    # Remover colunas da tabela auditorias
    op.drop_column("auditorias", "analise_completa")
    op.drop_column("auditorias", "classificacao_anexo")
    op.drop_column("auditorias", "folha_12m")
    op.drop_column("auditorias", "rbt12")
    op.drop_column("auditorias", "receita_pa")
    op.drop_column("auditorias", "aliquota_efetiva")
    op.drop_column("auditorias", "fator_r")
