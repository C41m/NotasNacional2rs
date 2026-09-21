from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.core.config import settings
from app.models.base import Base
from app.models.company import Company
from app.models.certificate import Certificate
from app.models.download_job import DownloadJob
from app.models.auditoria import Auditoria, AuditoriaPendencia
from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
from app.models.pgdas_d import PgdasD
from app.models.iss import Iss
from app.models.das import Das
from app.models.folha_pagamento import FolhaPagamento
from app.models.defis import Defis
from app.models.dirf import Dirf
from app.models.efd_reinf import EfdReinf
from app.models.documento_pendencia import DocumentoPendencia

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
