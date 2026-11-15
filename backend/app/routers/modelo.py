"""Endpoints de gestión del modelo (entrenamiento, versiones, métricas, rollback)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Modelo
from app.schemas import EntrenarRequest, EntrenarResponse, ModeloOut
from app.serializadores import serializar_modelo
from app.servicio_modelo import entrenar_nueva_version, modelo_activo

router = APIRouter(prefix="/modelo", tags=["modelo"])


@router.post("/entrenar", response_model=EntrenarResponse)
def entrenar(payload: EntrenarRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Reentrena el agente con todas las etiquetas vigentes y crea una versión nueva."""
    try:
        resultado = entrenar_nueva_version(db, forzar=payload.forzar, etiquetado_por=payload.etiquetado_por)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "activado": resultado["activado"],
        "motivo": resultado["motivo"],
        "version_nueva": serializar_modelo(resultado["version_nueva"]),
        "version_anterior": (
            serializar_modelo(resultado["version_anterior"])
            if resultado["version_anterior"] is not None
            else None
        ),
        "comparacion_algoritmos": resultado["comparacion_algoritmos"],
        "datos_suficientes": resultado["datos_suficientes"],
        "mensaje": resultado["mensaje"],
    }


@router.get("/activo", response_model=ModeloOut | None)
def obtener_activo(db: Session = Depends(get_db)) -> dict[str, Any] | None:
    """Devuelve la versión activa (o null si aún no hay modelo entrenado)."""
    modelo = modelo_activo(db)
    return serializar_modelo(modelo) if modelo else None


@router.get("/versiones", response_model=list[ModeloOut])
def listar_versiones(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Lista todas las versiones entrenadas, de la más reciente a la más antigua."""
    modelos = db.scalars(select(Modelo).order_by(Modelo.fecha.desc(), Modelo.id.desc())).all()
    return [serializar_modelo(m) for m in modelos]


@router.get("/metricas", response_model=ModeloOut | None)
def metricas(db: Session = Depends(get_db)) -> dict[str, Any] | None:
    """Métricas de la versión activa."""
    modelo = modelo_activo(db)
    return serializar_modelo(modelo) if modelo else None


@router.post("/{version}/activar", response_model=ModeloOut)
def activar_version(version: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Activa una versión concreta (rollback)."""
    objetivo = db.scalars(select(Modelo).where(Modelo.version == version)).first()
    if objetivo is None:
        raise HTTPException(status_code=404, detail=f"Versión {version} no encontrada")

    for modelo in db.scalars(select(Modelo).where(Modelo.activo.is_(True))).all():
        modelo.activo = False
    objetivo.activo = True
    db.commit()
    db.refresh(objetivo)
    return serializar_modelo(objetivo)
