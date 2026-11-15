"""Punto de entrada de la API del Kiosco Ciudadano (FastAPI).

El backend es el único cliente de la base de datos Supabase. El frontend
consume estos endpoints por HTTP (proxy de Vite hacia http://localhost:8000).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import etiquetado, estadisticas, modelo, predecir, solicitudes

app = FastAPI(
    title="Kiosco Ciudadano · API",
    description=(
        "API de clasificación de solicitudes ciudadanas mediante aprendizaje "
        "supervisado y procesamiento de lenguaje natural."
    ),
    version="1.0.0",
)

# CORS: solo se permite el origen del frontend de Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers bajo el prefijo /api.
app.include_router(solicitudes.router, prefix="/api")
app.include_router(etiquetado.router, prefix="/api")
app.include_router(modelo.router, prefix="/api")
app.include_router(estadisticas.router, prefix="/api")
app.include_router(predecir.router, prefix="/api")


@app.get("/api/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Comprobación rápida de disponibilidad del servicio."""
    return {"estado": "ok", "servicio": "kiosco-ciudadano-api"}
