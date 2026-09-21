from alembic import op
import sqlalchemy as sa

revision = "003_create_auditoria_tables"
down_revision = "002_add_notas_processed"


def upgrade():
    op.create_table(
        "auditorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cnpj", sa.String(14), nullable=False, index=True),
        sa.Column("razao_social", sa.String(255)),
        sa.Column("periodo", sa.String(7), nullable=False, index=True),
        sa.Column("status_geral", sa.String(20)),
        sa.Column("conformidade_pct", sa.Float()),
        sa.Column("observacao_geral", sa.Text(), nullable=True),
        sa.Column("documentos_esperados", sa.Integer()),
        sa.Column("documentos_encontrados", sa.Integer()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_auditorias_cnpj", "auditorias", ["cnpj"])
    op.create_index("ix_auditorias_periodo", "auditorias", ["periodo"])

    op.create_table(
        "auditoria_pendencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auditoria_id", sa.Integer(), sa.ForeignKey("auditorias.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_documento", sa.String(100)),
        sa.Column("gravidade", sa.String(10)),
        sa.Column("status", sa.String(20)),
        sa.Column("observacao", sa.Text()),
    )
    op.create_index("idx_auditoria_pendencias_auditoria", "auditoria_pendencias", ["auditoria_id"])


def downgrade():
    op.drop_table("auditoria_pendencias")
    op.drop_table("auditorias")
