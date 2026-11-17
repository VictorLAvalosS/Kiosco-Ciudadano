"""Seguridad de la API: verificación opcional de la clave (header X-API-Key).

Si la variable de entorno `API_KEY` está definida, los endpoints sensibles
(entrenar, activar versión, importar CSV, etiquetar) exigen la cabecera
`X-API-Key` con ese valor. Si `API_KEY` está vacía (desarrollo local), no se exige.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import settings


def verificar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Dependencia que valida la cabecera X-API-Key cuando hay clave configurada."""
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Clave de API inválida o ausente (cabecera X-API-Key).",
        )
