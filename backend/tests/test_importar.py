"""Pruebas de la importación de etiquetas desde CSV (con base de datos transaccional)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Etiqueta, Solicitud
from app.servicio_solicitudes import importar_solicitudes


def test_importar_valida_categoria_y_prioridad(db: Session) -> None:
    filas = [
        {"ID": "1", "Solicitud": "Fuga de agua en la calle principal", "Categoría": "Agua potable y alcantarillado", "Prioridad": "ALTA"},
        {"ID": "2", "Solicitud": "Categoría inexistente en el sistema", "Categoría": "Categoría Fantasma", "Prioridad": "MEDIA"},
        {"ID": "3", "Solicitud": "Prioridad mal escrita en la fila", "Categoría": "Alumbrado público", "Prioridad": "URGENTE"},
        {"ID": "4", "Solicitud": "abc", "Categoría": "Alumbrado público", "Prioridad": "BAJA"},
    ]

    resultado = importar_solicitudes(db, filas)

    assert resultado["total_filas"] == 4
    assert resultado["importadas"] == 1
    assert len(resultado["invalidas"]) == 3


def test_importar_tolera_tildes_y_mayusculas(db: Session) -> None:
    filas = [
        {"ID": "10", "Solicitud": "Basura acumulada junto al mercado", "Categoría": "LIMPIEZA Y RESIDUOS SOLIDOS", "Prioridad": "media"},
    ]
    resultado = importar_solicitudes(db, filas)
    assert resultado["importadas"] == 1


def test_importar_evita_duplicados_por_texto_normalizado(db: Session) -> None:
    texto = "Bache profundo en la avenida central"
    filas = [
        {"ID": "1", "Solicitud": texto, "Categoría": "Calles y vías públicas", "Prioridad": "ALTA"},
        {"ID": "2", "Solicitud": "BACHE PROFUNDO EN LA AVENIDA CENTRAL", "Categoría": "Calles y vías públicas", "Prioridad": "ALTA"},
    ]
    resultado = importar_solicitudes(db, filas)
    assert resultado["importadas"] == 1
    assert resultado["duplicadas"] == 1


def test_importar_crea_solicitud_y_etiqueta_vigente(db: Session) -> None:
    filas = [
        {"ID": "1", "Solicitud": "Canal de desague pluvial colapsado", "Categoría": "Drenaje y desagüe pluvial", "Prioridad": "ALTA"},
    ]
    importar_solicitudes(db, filas, etiquetado_por="Equipo Pruebas")

    solicitud = db.scalars(
        select(Solicitud).where(Solicitud.texto_normalizado == "canal de desague pluvial colapsado")
    ).first()
    assert solicitud is not None
    assert solicitud.origen == "importado"
    assert solicitud.ticket.startswith("SC-")

    etiqueta = db.scalars(
        select(Etiqueta).where(
            Etiqueta.solicitud_id == solicitud.id, Etiqueta.vigente.is_(True)
        )
    ).first()
    assert etiqueta is not None
    assert etiqueta.prioridad == "ALTA"
    assert etiqueta.etiquetado_por == "Equipo Pruebas"
