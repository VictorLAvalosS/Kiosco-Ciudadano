"""Endpoint de etiquetado: cola priorizada por aprendizaje activo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Etiqueta, Solicitud
from app.serializadores import serializar_solicitud

router = APIRouter(prefix="/etiquetado", tags=["etiquetado"])

# Metas de etiquetado por categoría (objetivo pedagógico de la materia).
META_POR_CATEGORIA = 50


@router.get("/guia")
def guia_etiquetado() -> dict[str, Any]:
    """Guía de criterios de etiquetado mostrada en la interfaz."""
    return {
        "prioridades": [
            {
                "nivel": "ALTA",
                "criterio": "Riesgo para personas o emergencia en curso.",
            },
            {
                "nivel": "MEDIA",
                "criterio": "Afecta el servicio desde hace días sin ser una emergencia.",
            },
            {
                "nivel": "BAJA",
                "criterio": "Mejora, mantenimiento o solicitud preventiva.",
            },
        ],
        "desambiguaciones": [
            {
                "categoria": "Agua potable y alcantarillado",
                "criterio": "Red de agua potable y aguas servidas/negras (tuberías, medidores, alcantarillado).",
            },
            {
                "categoria": "Drenaje y desagüe pluvial",
                "criterio": "Agua de lluvia, canales, cunetas y sumideros pluviales.",
            },
        ],
        "meta_por_categoria": META_POR_CATEGORIA,
    }


@router.get("/cola")
def cola_etiquetado(
    db: Session = Depends(get_db), limite: int = Query(default=25, ge=1, le=200)
) -> dict[str, Any]:
    """Cola priorizada de solicitudes por etiquetar (aprendizaje activo).

    Se priorizan las solicitudes SIN etiqueta vigente con menor confianza y menor
    margen entre las dos clases más probables: son las más informativas para el modelo.
    """
    sub = (
        select(Etiqueta.solicitud_id)
        .where(Etiqueta.vigente.is_(True))
        .scalar_subquery()
    )
    consulta = (
        select(Solicitud)
        .where(Solicitud.id.notin_(sub))
        .order_by(Solicitud.fecha.desc())
        .limit(600)
    )
    candidatas = list(db.scalars(consulta).all())

    def clave_orden(solicitud: Solicitud) -> tuple[float, float, float]:
        confianza = solicitud.confianza if solicitud.confianza is not None else 0.0
        margen = 100.0
        if isinstance(solicitud.probabilidades, dict):
            margen = float(solicitud.probabilidades.get("margen", 100.0))
        return (confianza, margen, -float(solicitud.id))

    candidatas.sort(key=clave_orden)
    seleccion = candidatas[:limite]

    return {
        "total_pendientes": len(candidatas),
        "meta_por_categoria": META_POR_CATEGORIA,
        "items": [
            {
                **serializar_solicitud(solicitud),
                "sugerencia_confirmar": (
                    solicitud.categoria_predicha.clave if solicitud.categoria_predicha else None
                ),
                "margen": (
                    solicitud.probabilidades.get("margen")
                    if isinstance(solicitud.probabilidades, dict)
                    else None
                ),
            }
            for solicitud in seleccion
        ],
    }
