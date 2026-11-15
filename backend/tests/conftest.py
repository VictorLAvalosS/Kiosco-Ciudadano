"""Fixtures compartidas de las pruebas del backend.

Cada prueba se ejecuta dentro de una transacción externa que SIEMPRE se revierte
al terminar, de modo que la base de datos real (Supabase) no queda contaminada.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.categorias import CATEGORIAS_SEED
from app.database import engine, get_db
from app.main import app
from app.models import Categoria, Etiqueta, Solicitud
from app.servicio_solicitudes import generar_ticket
from ml.preprocesamiento import normalizar


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Sesión de base de datos con reversión garantizada al final de la prueba."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    # `create_savepoint` permite que los commit() internos no cierren la transacción externa.
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP de pruebas con la sesión transaccional inyectada."""

    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def categorias(db: Session) -> dict[str, Categoria]:
    """Mapa clave -> Categoria desde la base de datos."""
    return {c.clave: c for c in db.query(Categoria).all()}


def crear_dataset_etiquetado(
    db: Session, por_categoria: int, etiquetado_por: str = "Pruebas"
) -> list[Solicitud]:
    """Crea solicitudes con etiqueta vigente para las pruebas de entrenamiento.

    Genera `por_categoria` solicitudes por cada una de las 8 categorías, con textos
    distintos pero claramente asociados a su categoría.
    """
    categorias = {c.clave: c for c in db.query(Categoria).all()}
    creadas: list[Solicitud] = []

    for indice, info in enumerate(CATEGORIAS_SEED):
        clave = info["clave"]
        categoria = categorias[clave]
        for numero in range(por_categoria):
            texto = f"solicitud {clave} numero {numero} caso de prueba {indice}"
            solicitud = Solicitud(
                ticket="",
                texto=texto,
                texto_normalizado=normalizar(texto),
                otb="OTB Central",
                zona="Zona 1",
                estado="Sin asignar",
                origen="importado",
            )
            db.add(solicitud)
            db.flush()
            solicitud.ticket = generar_ticket(db, solicitud.id)
            db.add(
                Etiqueta(
                    solicitud_id=solicitud.id,
                    categoria_id=categoria.id,
                    prioridad="MEDIA",
                    etiquetado_por=etiquetado_por,
                    vigente=True,
                )
            )
            creadas.append(solicitud)

    db.commit()
    return creadas
