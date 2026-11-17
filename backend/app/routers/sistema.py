"""Endpoints de sistema: salud real, calidad del dataset, acuerdo y experimentos."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from fastapi import APIRouter, Depends
from sklearn.metrics import cohen_kappa_score
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Categoria, Etiqueta, ExperimentoMejora, Solicitud
from app.schemas import AcuerdoOut, CalidadDatasetOut, SaludOut
from app.servicio_modelo import etiquetas_vigentes, modelo_activo
from ml import calidad

router = APIRouter(tags=["sistema"])


@router.get("/salud", response_model=SaludOut)
def salud(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Estado REAL del sistema: base de datos, modelo activo y nº de etiquetas."""
    try:
        db.execute(text("SELECT 1"))
        estado_bd = "conectada"
    except Exception:  # pragma: no cover - depende de la conexión
        estado_bd = "error"

    activo = modelo_activo(db)
    n_etiquetas = int(
        db.scalar(
            select(func.count()).select_from(Etiqueta).where(Etiqueta.vigente.is_(True))
        )
        or 0
    )

    return {
        "estado": "ok" if estado_bd == "conectada" else "degradado",
        "servicio": "kiosco-ciudadano-api",
        "base_datos": estado_bd,
        "version_modelo": activo.version if activo else None,
        "n_etiquetas": n_etiquetas,
        "umbral_confianza": settings.umbral_confianza,
        "umbral_margen": settings.umbral_margen,
        "api_key_activa": bool(settings.api_key),
    }


@router.get("/calidad-dataset", response_model=CalidadDatasetOut)
def calidad_dataset(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Informe de calidad del dataset etiquetado (duplicados, desbalance, etc.)."""
    return calidad.informe_calidad(etiquetas_vigentes(db))


@router.get("/acuerdo-etiquetadores", response_model=AcuerdoOut)
def acuerdo_etiquetadores(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Consistencia entre personas del equipo (kappa de Cohen sobre categoría/prioridad).

    Se consideran las solicitudes etiquetadas por 2 o más personas (utilizando la
    última etiqueta de cada persona). Con un solo etiquetador por solicitud no es
    posible calcular el acuerdo y se informa explícitamente.
    """
    filas = db.execute(
        select(
            Etiqueta.solicitud_id,
            Etiqueta.etiquetado_por,
            Etiqueta.fecha,
            Categoria.clave,
            Etiqueta.prioridad,
            Solicitud.texto,
        )
        .join(Categoria, Categoria.id == Etiqueta.categoria_id)
        .join(Solicitud, Solicitud.id == Etiqueta.solicitud_id)
        .order_by(Etiqueta.solicitud_id, Etiqueta.fecha)
    ).all()

    # Última etiqueta por (solicitud, etiquetador).
    por_solicitud: dict[int, dict[str, tuple[str, str, str]]] = defaultdict(dict)
    for solicitud_id, etiquetador, _fecha, clave, prioridad, texto in filas:
        por_solicitud[int(solicitud_id)][etiquetador or "Sin nombre"] = (
            clave,
            prioridad,
            texto,
        )

    dobles = {sid: mapa for sid, mapa in por_solicitud.items() if len(mapa) >= 2}

    # Pares de etiquetadores que coinciden en al menos una solicitud.
    pares_categoria: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    pares_prioridad: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    discrepancias: list[dict[str, Any]] = []
    etiquetadores: set[str] = set()

    for solicitud_id, mapa in dobles.items():
        etiquetadores.update(mapa.keys())
        nombres = sorted(mapa.keys())
        categorias = {nombre: mapa[nombre][0] for nombre in nombres}
        prioridades = {nombre: mapa[nombre][1] for nombre in nombres}
        if len(set(categorias.values())) > 1:
            discrepancias.append(
                {
                    "solicitud_id": solicitud_id,
                    "texto": mapa[nombres[0]][2],
                    "etiquetas": [
                        {"etiquetador": n, "categoria": categorias[n], "prioridad": prioridades[n]}
                        for n in nombres
                    ],
                }
            )
        for a, b in combinations(nombres, 2):
            pares_categoria[(a, b)].append((categorias[a], categorias[b]))
            pares_prioridad[(a, b)].append((prioridades[a], prioridades[b]))

    def _kappa_promedio(
        pares: dict[tuple[str, str], list[tuple[str, str]]],
    ) -> tuple[float, float] | None:
        """Promedio de kappa de Cohen por par de etiquetadores, ponderado por casos.

        Devuelve (kappa_promedio, acuerdo_observado) o None si no hay pares.
        """
        total, acumulado, acuerdos = 0, 0.0, 0
        for observaciones in pares.values():
            if len(observaciones) < 2:
                continue
            a = [o[0] for o in observaciones]
            b = [o[1] for o in observaciones]
            acumulado += float(cohen_kappa_score(a, b)) * len(observaciones)
            acuerdos += sum(1 for x, y in observaciones if x == y)
            total += len(observaciones)
        if total == 0:
            return None
        return round(acumulado / total, 4), round(acuerdos / total, 4)

    kappa_cat = _kappa_promedio(pares_categoria)
    kappa_pri = _kappa_promedio(pares_prioridad)

    mensaje = ""
    if not dobles:
        mensaje = (
            "Aún no hay solicitudes etiquetadas por dos o más personas, por lo que no "
            "se puede calcular el acuerdo. Para medirlo, dos integrantes deben etiquetar "
            "el mismo conjunto de solicitudes."
        )

    return {
        "kappa_categoria": kappa_cat[0] if kappa_cat else None,
        "kappa_prioridad": kappa_pri[0] if kappa_pri else None,
        "puntuacion_observada_categoria": kappa_cat[1] if kappa_cat else None,
        "puntuacion_observada_prioridad": kappa_pri[1] if kappa_pri else None,
        "n_solicitudes_dobles": len(dobles),
        "n_etiquetadores": len(etiquetadores),
        "discrepancias": discrepancias[:20],
        "mensaje": mensaje,
    }


@router.get("/experimentos")
def listar_experimentos(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Experimentos guardados (p. ej. la demostración de mejora por volumen)."""
    filas = db.scalars(
        select(ExperimentoMejora).order_by(ExperimentoMejora.fecha.desc(), ExperimentoMejora.id.desc())
    ).all()
    return [
        {
            "id": fila.id,
            "fecha": fila.fecha,
            "tipo": fila.tipo,
            "n_total": fila.n_total,
            "resultado": fila.resultado,
        }
        for fila in filas
    ]
