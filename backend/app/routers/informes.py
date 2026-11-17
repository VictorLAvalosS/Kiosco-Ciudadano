"""Endpoints del informe del agente (Fase A5).

Permite generar el informe (Markdown + JSON) desde la interfaz, consultar el
historial, ver el estado de una generación en segundo plano y descargarlo en
`.md`, `.json` o `.zip` (con los CSV de las matrices de confusión).

Todos los endpoints están protegidos con la clave de API (`X-API-Key`) cuando el
backend tiene configurada `API_KEY`.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Informe
from app.schemas import (
    InformeGenerarRequest,
    InformeGenerarResponse,
    InformeOut,
    InformeResumenOut,
)
from app.seguridad import verificar_api_key
from app.servicio_informe import (
    construir_zip,
    generar_informe,
    generar_y_guardar,
    nombre_archivo,
)

router = APIRouter(prefix="/informe", tags=["informe"])


def _generar_en_segundo_plano(informe_id: int, opciones: dict[str, Any]) -> None:
    """Genera el informe en segundo plano con una sesión propia y guarda el estado."""
    with SessionLocal() as db:
        informe = db.get(Informe, informe_id)
        if informe is None:  # pragma: no cover - el registro se crea antes de lanzar
            return
        try:
            resultado = generar_informe(db, opciones)
            informe.contenido_md = resultado["markdown"]
            informe.contenido_json = resultado["json"]
            informe.version_modelo = resultado["version_modelo"]
            informe.estado = "completado"
            informe.error = ""
        except Exception as error:  # pragma: no cover - depende de los datos
            informe.estado = "error"
            informe.error = str(error)[:300]
        db.commit()


@router.post(
    "/generar",
    response_model=InformeGenerarResponse,
    dependencies=[Depends(verificar_api_key)],
)
def generar(
    payload: InformeGenerarRequest,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Genera y guarda un informe del agente.

    Con `segundo_plano=true` devuelve el id inmediatamente y el estado se consulta
    en `GET /api/informe/{id}/estado`; en caso contrario se genera de forma
    síncrona (la generación no reentrena nada, por lo que suele ser rápida).
    """
    opciones = {
        "textos_ejemplo": payload.textos_ejemplo,
        "generado_por": payload.generado_por,
    }

    if payload.segundo_plano:
        informe = Informe(
            version_modelo="",
            generado_por=payload.generado_por,
            estado="en_proceso",
            opciones={
                "textos_ejemplo": payload.textos_ejemplo,
                "generado_por": payload.generado_por,
            },
        )
        db.add(informe)
        db.commit()
        db.refresh(informe)
        tareas.add_task(_generar_en_segundo_plano, informe.id, opciones)
        return {"id": informe.id, "estado": informe.estado}

    informe = generar_y_guardar(db, opciones)
    if informe.estado == "error":
        raise HTTPException(
            status_code=500,
            detail=informe.error or "No se pudo generar el informe del agente.",
        )
    return {"id": informe.id, "estado": informe.estado}


@router.get("", response_model=list[InformeResumenOut], dependencies=[Depends(verificar_api_key)])
def historial(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Historial de informes generados, del más reciente al más antiguo."""
    filas = db.scalars(
        select(Informe).order_by(Informe.fecha.desc(), Informe.id.desc())
    ).all()
    return [
        {
            "id": fila.id,
            "fecha": fila.fecha,
            "version_modelo": fila.version_modelo,
            "generado_por": fila.generado_por,
            "estado": fila.estado,
            "error": fila.error,
        }
        for fila in filas
    ]


@router.get("/{informe_id}/estado", dependencies=[Depends(verificar_api_key)])
def estado(informe_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Estado actual de una generación (en_proceso | completado | error)."""
    informe = db.get(Informe, informe_id)
    if informe is None:
        raise HTTPException(status_code=404, detail=f"Informe {informe_id} no encontrado")
    return {"id": informe.id, "estado": informe.estado, "error": informe.error}


@router.get("/{informe_id}", response_model=InformeOut, dependencies=[Depends(verificar_api_key)])
def obtener(informe_id: int, db: Session = Depends(get_db)) -> Informe:
    """Contenido completo de un informe (Markdown + JSON estructurado)."""
    informe = db.get(Informe, informe_id)
    if informe is None:
        raise HTTPException(status_code=404, detail=f"Informe {informe_id} no encontrado")
    return informe


@router.get("/{informe_id}/descargar", dependencies=[Depends(verificar_api_key)])
def descargar(
    informe_id: int,
    formato: str = Query("md", pattern="^(md|json|zip)$"),
    db: Session = Depends(get_db),
) -> Response:
    """Descarga el informe en Markdown, JSON o ZIP (con los CSV de las matrices)."""
    informe = db.get(Informe, informe_id)
    if informe is None:
        raise HTTPException(status_code=404, detail=f"Informe {informe_id} no encontrado")
    if informe.estado != "completado":
        raise HTTPException(
            status_code=409,
            detail=f"El informe {informe_id} no está completado (estado: {informe.estado}).",
        )

    if formato == "md":
        contenido = (informe.contenido_md or "").encode("utf-8")
        media = "text/markdown; charset=utf-8"
    elif formato == "json":
        contenido = json.dumps(
            informe.contenido_json or {}, ensure_ascii=False, indent=2
        ).encode("utf-8")
        media = "application/json; charset=utf-8"
    else:
        contenido = construir_zip(informe)
        media = "application/zip"

    archivo = nombre_archivo(informe, formato)
    return Response(
        content=contenido,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{archivo}"'},
    )
