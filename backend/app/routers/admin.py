"""Acceso del administrador: valida la clave contra Supabase Authentication."""
import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

load_dotenv()

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginIn(BaseModel):
    password: str


def _config() -> tuple[str, str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    clave = os.environ.get("SUPABASE_ANON_KEY", "")
    correo = os.environ.get("ADMIN_EMAIL", "")
    if not (url and clave and correo):
        raise HTTPException(503, "Falta SUPABASE_URL, SUPABASE_ANON_KEY o ADMIN_EMAIL en backend/.env.")
    return url, clave, correo


@router.post("/login")
def login(datos: LoginIn) -> dict[str, str]:
    url, clave, correo = _config()
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
    return {"token": r.json()["access_token"]}


def exigir_admin(authorization: str | None = Header(default=None)) -> None:
    """Dependencia opcional para proteger endpoints: Depends(exigir_admin)."""
    url, clave, correo = _config()
    if not authorization:
        raise HTTPException(401, "Se requiere iniciar sesión como administrador.")
    r = httpx.get(
        f"{url}/auth/v1/user",
        headers={"apikey": clave, "Authorization": authorization},
        timeout=10,
    )
    if r.status_code != 200 or r.json().get("email") != correo:
        raise HTTPException(401, "Sesión de administrador inválida.")