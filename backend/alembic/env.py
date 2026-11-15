"""Entorno de ejecución de Alembic.

Toma la URL de conexión desde las variables de entorno (backend/.env) y
expone los metadatos de los modelos ORM para autogenerar migraciones.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# Importar los modelos registra las tablas en Base.metadata.
import app.models  # noqa: F401  (import necesario por efecto secundario)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La URL se toma SIEMPRE de la variable de entorno.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta las migraciones en modo 'offline' (sin conexión activa)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones en modo 'online' (con conexión real)."""
    configuracion = config.get_section(config.config_ini_section, {})
    conectable = engine_from_config(
        configuracion, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with conectable.connect() as conexion:
        context.configure(
            connection=conexion, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
