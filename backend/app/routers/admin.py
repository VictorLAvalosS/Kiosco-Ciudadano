"""Acceso del administrador: valida la clave en modo local o contra Supabase si está configurado."""

from __future__ import annotations

import os
import secrets

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

# Token local fijo para la sesión del administrador en modo local.
LOCAL_ADMIN_TOKEN = "local-admin-token"


class LoginIn(BaseModel):
    password: str


def _usa_supabase() -> bool:
    """Indica si se deben usar credenciales de Supabase Auth en lugar de la clave local."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    clave = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    correo = os.environ.get("ADMIN_EMAIL", "").strip()
    return bool(url and clave and correo)


def _config_supabase() -> tuple[str, str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    clave = os.environ.get("SUPABASE_ANON_KEY", "")
    correo = os.environ.get("ADMIN_EMAIL", "")
    if not (url and clave and correo):
        raise HTTPException(
            503, "Falta SUPABASE_URL, SUPABASE_ANON_KEY o ADMIN_EMAIL en backend/.env."
        )
    return url, clave, correo


@router.post("/login")
def login(datos: LoginIn) -> dict[str, str]:
    # Modo local: validación con ADMIN_PASSWORD (por defecto 'admin')
    if not _usa_supabase():
        clave_esperada = settings.admin_password or "admin"
        if secrets.compare_digest(datos.password, clave_esperada):
            return {"token": LOCAL_ADMIN_TOKEN}
        raise HTTPException(401, "Contraseña incorrecta.")

    # Modo Supabase Auth (si está explícitamente configurado)
    url, clave, correo = _config_supabase()
    try:
        r = httpx.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": clave},
            json={"email": correo, "password": datos.password},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "No se pudo contactar con Supabase Auth.")
    if r.status_code in (400, 401, 422):
        raise HTTPException(401, "Contraseña incorrecta.")
    if r.status_code != 200:
        raise HTTPException(502, "Supabase Auth no respondió correctamente.")
    return {"token": r.json().get("access_token", LOCAL_ADMIN_TOKEN)}


def exigir_admin(authorization: str | None = Header(default=None)) -> None:
    """Dependencia opcional para proteger endpoints: Depends(exigir_admin)."""
    if not authorization:
        raise HTTPException(401, "Se requiere iniciar sesión como administrador.")

    if not _usa_supabase():
        token_recibido = authorization.removeprefix("Bearer ").strip()
        if token_recibido == LOCAL_ADMIN_TOKEN:
            return
        raise HTTPException(401, "Sesión de administrador inválida.")

    url, clave, correo = _config_supabase()
    r = httpx.get(
        f"{url}/auth/v1/user",
        headers={"apikey": clave, "Authorization": authorization},
        timeout=10,
    )
    if r.status_code != 200 or r.json().get("email") != correo:
        raise HTTPException(401, "Sesión de administrador inválida.")
