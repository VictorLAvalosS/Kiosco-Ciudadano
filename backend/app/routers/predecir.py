"""Endpoint de predicción sin persistencia (inspector NLP)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PredecirRequest, PredecirResponse
from app.servicio_modelo import predecir_con_explicacion

router = APIRouter(tags=["predecir"])


@router.post("/predecir", response_model=PredecirResponse)
def predecir(payload: PredecirRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Ejecuta el pipeline NLP real sobre un texto y devuelve la explicación."""
    prediccion = predecir_con_explicacion(db, payload.texto)
    if prediccion is None:
        raise HTTPException(
            status_code=409,
            detail="Todavía no hay un modelo entrenado. Entrena el agente desde el panel de IA.",
        )

    return prediccion
