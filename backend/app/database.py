"""Configuración de la conexión a la base de datos (SQLAlchemy 2.x).

El backend es el único cliente de la base de datos: el frontend nunca se conecta
directamente. Toda la persistencia pasa por el ORM de SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Motor de conexión. `pool_pre_ping` evita usar conexiones caídas (útil en Supabase).
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=1800,
    connect_args={"connect_timeout": 10},
    future=True,
)

# Fábrica de sesiones. `expire_on_commit=False` permite leer los objetos tras el commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base declarativa de todos los modelos ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI que entrega una sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
