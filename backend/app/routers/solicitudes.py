"""Endpoints de solicitudes, categorías y etiquetado."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorias import ESTADOS_VALIDOS
from app.database import get_db
from app.models import Categoria, Etiqueta, Solicitud
from app.schemas import (
    AsignarRequest,
    CategoriaOut,
    EstadoUpdate,
    EtiquetaCreate,
    ImportarResponse,
    SolicitudCreate,
    SolicitudOut,
)
from app.serializadores import serializar_etiqueta, serializar_solicitud
from app.servicio_modelo import predecir_con_explicacion
from app.servicio_solicitudes import (
    importar_solicitudes,
    mapa_categorias,
    normalizar_clave,
    registrar_etiqueta,
    resolver_categoria,
)
from ml.preprocesamiento import normalizar

router = APIRouter(tags=["solicitudes"])


@router.get("/categorias", response_model=list[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)) -> list[Categoria]:
    """Devuelve las 8 categorías municipales."""
    return list(db.scalars(select(Categoria).order_by(Categoria.id)).all())


@router.post("/solicitudes", response_model=SolicitudOut)
def crear_solicitud(payload: SolicitudCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Crea una solicitud, la clasifica con el modelo activo y guarda todo."""
    solicitud = Solicitud(
        ticket="",
        texto=payload.texto,
        texto_normalizado=normalizar(payload.texto),
        otb=payload.otb or "Sin OTB",
        zona=payload.zona or "Sin zona",
        estado="Sin asignar",
        origen=payload.origen,
    )
    db.add(solicitud)
    db.flush()
    solicitud.ticket = f"SC-2025-{solicitud.id:04d}"

    # Predicción con el modelo activo (latencia realmente medida).
    prediccion = predecir_con_explicacion(db, payload.texto)
    if prediccion is not None:
        categorias = mapa_categorias(db)
        categoria = categorias.get(prediccion["categoria"])
        solicitud.categoria_predicha_id = categoria.id if categoria else None
        solicitud.prioridad_predicha = prediccion["prioridad"]
        solicitud.confianza = prediccion["confianza"]
        solicitud.probabilidades = {
            "ranking": prediccion["probabilidades"],
            "margen": prediccion["margen"],
            "ranking_prioridad": prediccion["probabilidades_prioridad"],
        }
        solicitud.version_modelo = prediccion["version_modelo"]
        solicitud.latencia_ms = prediccion["latencia_ms"]

    db.commit()
    db.refresh(solicitud)
    return serializar_solicitud(solicitud, prediccion_detalle=prediccion)


@router.get("/solicitudes", response_model=list[SolicitudOut])
def listar_solicitudes(
    db: Session = Depends(get_db),
    estado: str | None = None,
    categoria: str | None = None,
    etiquetada: bool | None = None,
    confianza_max: float | None = Query(default=None, ge=0, le=100),
    origen: str | None = None,
    texto: str | None = None,
    limite: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    """Lista solicitudes con filtros opcionales."""
    sub = (
        select(Etiqueta.solicitud_id.label("sid"), Etiqueta.id.label("eid"))
        .where(Etiqueta.vigente.is_(True))
        .subquery()
    )
    consulta = (
        select(Solicitud, Etiqueta)
        .outerjoin(sub, sub.c.sid == Solicitud.id)
        .outerjoin(Etiqueta, Etiqueta.id == sub.c.eid)
    )

    if estado:
        consulta = consulta.where(Solicitud.estado == estado)
    if origen:
        consulta = consulta.where(Solicitud.origen == origen)
    if confianza_max is not None:
        consulta = consulta.where(Solicitud.confianza <= confianza_max)
    if etiquetada is True:
        consulta = consulta.where(sub.c.eid.isnot(None))
    elif etiquetada is False:
        consulta = consulta.where(sub.c.eid.is_(None))
    if texto:
        patron = f"%{normalizar(texto)}%"
        consulta = consulta.where(Solicitud.texto_normalizado.like(patron))
    if categoria:
        objetivo = normalizar_clave(categoria)
        consulta = consulta.join(Categoria, Categoria.id == Solicitud.categoria_predicha_id).where(
            Categoria.clave == objetivo
        )

    consulta = consulta.order_by(Solicitud.fecha.desc()).limit(limite)
    filas = db.execute(consulta).all()
    return [serializar_solicitud(fila[0], fila[1]) for fila in filas]


@router.patch("/solicitudes/{solicitud_id}/estado", response_model=SolicitudOut)
def cambiar_estado(
    solicitud_id: int, payload: EstadoUpdate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Actualiza el estado operativo de una solicitud."""
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if payload.estado not in ESTADOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    solicitud.estado = payload.estado
    db.commit()
    db.refresh(solicitud)
    return serializar_solicitud(solicitud, _etiqueta_vigente(db, solicitud_id))


@router.patch("/solicitudes/{solicitud_id}/asignar", response_model=SolicitudOut)
def asignar_solicitud(
    solicitud_id: int, payload: AsignarRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Asigna una solicitud a una cuadrilla y la marca como asignada."""
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    solicitud.estado = "Asignado"
    db.commit()
    db.refresh(solicitud)
    return serializar_solicitud(solicitud, _etiqueta_vigente(db, solicitud_id))


@router.post("/solicitudes/{solicitud_id}/etiqueta", response_model=SolicitudOut)
def etiquetar_solicitud(
    solicitud_id: int, payload: EtiquetaCreate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Fija la categoría y prioridad correctas de una solicitud (guarda quién)."""
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    categoria = resolver_categoria(db, payload.categoria_clave)
    if categoria is None:
        raise HTTPException(status_code=400, detail=f"Categoría desconocida: {payload.categoria_clave}")
    if payload.prioridad not in ("ALTA", "MEDIA", "BAJA"):
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    registrar_etiqueta(db, solicitud, categoria, payload.prioridad, payload.etiquetado_por)
    db.commit()
    db.refresh(solicitud)
    return serializar_solicitud(solicitud, _etiqueta_vigente(db, solicitud_id))


@router.post("/solicitudes/importar", response_model=ImportarResponse)
async def importar(peticion: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Importa etiquetas desde un CSV (columnas: ID, Solicitud, Categoría, Prioridad).

    Acepta:
      * `Content-Type: text/csv` con el CSV en el cuerpo.
      * `application/json` con `{"csv": "..."}` o `{"filas": [{...}, ...]}`.
    """
    contenido = (await peticion.body()).decode("utf-8-sig")
    tipo = peticion.headers.get("content-type", "")

    filas: list[dict[str, str]] = []
    if "application/json" in tipo:
        datos = json.loads(contenido or "{}")
        if "filas" in datos:
            filas = [dict(f) for f in datos["filas"]]
        else:
            filas = [dict(f) for f in csv.DictReader(io.StringIO(datos.get("csv", "")))]
    else:
        filas = [dict(f) for f in csv.DictReader(io.StringIO(contenido))]

    if not filas:
        raise HTTPException(status_code=400, detail="No se recibieron filas para importar")

    etiquetador = "Importación CSV"
    return importar_solicitudes(db, filas, etiquetador)


def _etiqueta_vigente(db: Session, solicitud_id: int) -> Etiqueta | None:
    """Etiqueta vigente de una solicitud."""
    return db.scalars(
        select(Etiqueta).where(
            Etiqueta.solicitud_id == solicitud_id, Etiqueta.vigente.is_(True)
        )
    ).first()


@router.get("/solicitudes/{solicitud_id}", response_model=SolicitudOut)
def obtener_solicitud(solicitud_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Devuelve una solicitud por su id."""
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return serializar_solicitud(solicitud, _etiqueta_vigente(db, solicitud_id))


__all__ = ["router", "serializar_etiqueta"]
