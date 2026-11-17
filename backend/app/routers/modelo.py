"""Endpoints de gestión del modelo (entrenamiento, versiones, métricas, rollback)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Modelo
from app.schemas import EntrenarRequest, EntrenarResponse, ModeloOut
from app.seguridad import verificar_api_key
from app.serializadores import serializar_modelo
from app.servicio_modelo import (
    entrenar_nueva_version,
    modelo_activo,
    parametros_modelo_activo,
    reevaluar_versiones,
)

router = APIRouter(prefix="/modelo", tags=["modelo"])


@router.post("/entrenar", response_model=EntrenarResponse, dependencies=[Depends(verificar_api_key)])
def entrenar(payload: EntrenarRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Reentrena el agente con todas las etiquetas vigentes y crea una versión nueva."""
    try:
        resultado = entrenar_nueva_version(db, forzar=payload.forzar, etiquetado_por=payload.etiquetado_por)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    # Opción: generar y guardar un informe del agente al terminar el reentrenamiento.
    if payload.generar_informe:
        from app.servicio_informe import generar_y_guardar

        generar_y_guardar(db, {"generado_por": payload.etiquetado_por or "Reentrenamiento"})

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


@router.get("/parametros")
def parametros(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Parámetros completos del modelo activo (Fase A2).

    Algoritmo ganador, hiperparámetros reales (C, ngram_range, min_df,
    class_weight), tamaño del vocabulario TF-IDF, división de datos, semilla,
    umbrales, comparación de los 3 algoritmos y eficiencia medida (Fase A3).
    """
    datos = parametros_modelo_activo(db)
    if datos is None:
        raise HTTPException(
            status_code=409,
            detail="Todavía no hay un modelo activo. Entrena el agente para ver sus parámetros.",
        )
    return datos


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


@router.post("/reevaluar", dependencies=[Depends(verificar_api_key)])
def reevaluar(db: Session = Depends(get_db), regenerar: bool = False) -> dict[str, Any]:
    """Reevalúa todas las versiones sobre el conjunto de prueba fijo actual.

    Por defecto REUTILIZA el conjunto de prueba fijo vigente (para no alterarlo);
    con `?regenerar=true` crea una nueva generación por grupos de casi-duplicados
    y recalcula las métricas de cada versión, de modo que el historial quede
    comparable (Fase 1.2-1.3).
    """
    actualizados = reevaluar_versiones(db, regenerar_prueba=regenerar)
    return {"versiones": actualizados, "total": len(actualizados)}


@router.post("/{version}/activar", response_model=ModeloOut, dependencies=[Depends(verificar_api_key)])
def activar_version(
    version: str, forzar: bool = False, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Activa una versión concreta (rollback).

    Una versión marcada como NO comparable (entrenada con datos del conjunto de
    prueba) no puede activarse salvo que se fuerce con `?forzar=true`.
    """
    objetivo = db.scalars(select(Modelo).where(Modelo.version == version)).first()
    if objetivo is None:
        raise HTTPException(status_code=404, detail=f"Versión {version} no encontrada")

    if not objetivo.valida_para_comparacion and not forzar:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La versión {version} no es comparable "
                f"({objetivo.motivo_invalidez or 'entrenada con datos del conjunto de prueba'}). "
                "Usa ?forzar=true para activarla de todos modos."
            ),
        )

    for modelo in db.scalars(select(Modelo).where(Modelo.activo.is_(True))).all():
        modelo.activo = False
    objetivo.activo = True
    db.commit()
    db.refresh(objetivo)
    return serializar_modelo(objetivo)
