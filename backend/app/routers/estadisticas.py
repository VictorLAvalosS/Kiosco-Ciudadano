"""Endpoint de estadísticas generales del sistema."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.categorias import CATEGORIAS_SEED
from app.database import get_db
from app.models import Categoria, Etiqueta, Solicitud
from app.routers.etiquetado import META_POR_CATEGORIA
from app.servicio_modelo import modelo_activo
from ml.entrenamiento import MINIMO_POR_CLASE

router = APIRouter(tags=["estadisticas"])


@router.get("/estadisticas")
def estadisticas(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Resumen real del dataset y del progreso de etiquetado."""
    total = int(db.scalar(select(func.count()).select_from(Solicitud)) or 0)

    sub_vigentes = select(Etiqueta.solicitud_id).where(Etiqueta.vigente.is_(True)).scalar_subquery()
    etiquetadas = int(
        db.scalar(
            select(func.count()).select_from(Solicitud).where(Solicitud.id.in_(sub_vigentes))
        )
        or 0
    )

    # Conteo por categoría (etiquetas vigentes).
    filas_categoria = db.execute(
        select(Categoria.clave, Categoria.nombre, Categoria.icono, func.count(Etiqueta.id))
        .join(Etiqueta, Etiqueta.categoria_id == Categoria.id)
        .where(Etiqueta.vigente.is_(True))
        .group_by(Categoria.clave, Categoria.nombre, Categoria.icono)
    ).all()
    conteo = {fila[0]: {"nombre": fila[1], "icono": fila[2], "total": int(fila[3])} for fila in filas_categoria}

    por_categoria = [
        {
            "clave": c["clave"],
            "nombre": c["nombre"],
            "icono": c["icono"],
            "total": conteo.get(c["clave"], {}).get("total", 0),
        }
        for c in CATEGORIAS_SEED
    ]

    progreso = [
        {
            "clave": item["clave"],
            "nombre": item["nombre"],
            "etiquetadas": item["total"],
            "meta": META_POR_CATEGORIA,
            "faltan": max(0, META_POR_CATEGORIA - item["total"]),
        }
        for item in por_categoria
    ]

    # Conteo por etiquetador.
    filas_etiquetador = db.execute(
        select(Etiqueta.etiquetado_por, func.count(Etiqueta.id))
        .where(Etiqueta.vigente.is_(True))
        .group_by(Etiqueta.etiquetado_por)
        .order_by(func.count(Etiqueta.id).desc())
    ).all()
    por_etiquetador = [
        {"nombre": fila[0] or "Sin nombre", "total": int(fila[1])} for fila in filas_etiquetador
    ]

    activo = modelo_activo(db)
    etiquetas_desde_entrenamiento = 0
    if activo is not None:
        etiquetas_desde_entrenamiento = int(
            db.scalar(
                select(func.count())
                .select_from(Etiqueta)
                .where(Etiqueta.vigente.is_(True), Etiqueta.fecha > activo.fecha)
            )
            or 0
        )

    minimo_por_clase = min((item["total"] for item in por_categoria), default=0)

    return {
        "total_solicitudes": total,
        "etiquetadas": etiquetadas,
        "sin_etiquetar": max(0, total - etiquetadas),
        "por_categoria": por_categoria,
        "por_etiquetador": por_etiquetador,
        "etiquetas_desde_ultimo_entrenamiento": etiquetas_desde_entrenamiento,
        "version_activa": activo.version if activo else None,
        "datos_suficientes": minimo_por_clase >= MINIMO_POR_CLASE,
        "progreso_por_categoria": progreso,
    }
