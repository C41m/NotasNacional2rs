from alembic import op
import sqlalchemy as sa

revision = "001_initial_migration"
down_revision = None

def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index("ix_companies_cnpj", "companies", ["cnpj"])

    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), unique=True),
        sa.Column("certificado_enc", sa.Text(), nullable=False),
        sa.Column("senha_enc", sa.Text(), nullable=False),
        sa.Column("validade", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )

    op.create_table(
        "download_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("file_url", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index("idx_download_jobs_company", "download_jobs", ["company_id"])

def downgrade():
    op.drop_table("download_jobs")
    op.drop_table("certificates")
    op.drop_table("companies")
