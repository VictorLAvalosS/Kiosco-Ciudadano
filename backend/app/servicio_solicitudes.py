"""Servicios de negocio para solicitudes ciudadanas.

Agrupa: normalización, generación de tickets, creación con predicción,
asignación de etiquetas (con historial) e importación desde CSV.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.categorias import CLAVES_VALIDAS, ESTADOS_VALIDOS, PRIORIDADES_VALIDAS
from app.models import Categoria, Etiqueta, Solicitud, UsuarioEtiquetador
from ml.preprocesamiento import normalizar


def normalizar_clave(valor: str) -> str:
    """Normaliza una categoría o prioridad escrita a mano (tolerando tildes/mayúsculas)."""
    return normalizar(valor).replace(" ", "_")


def mapa_categorias(db: Session) -> dict[str, Categoria]:
    """Devuelve un diccionario `clave -> Categoria` con todas las categorías."""
    categorias = db.scalars(select(Categoria)).all()
    return {c.clave: c for c in categorias}


def resolver_categoria(db: Session, texto: str) -> Categoria | None:
    """Resuelve una categoría por su clave o por su nombre (tolerante a tildes)."""
    objetivo = normalizar_clave(texto)
    for categoria in db.scalars(select(Categoria)).all():
        if normalizar_clave(categoria.clave) == objetivo:
            return categoria
        if normalizar_clave(categoria.nombre) == objetivo:
            return categoria
    return None


def generar_ticket(db: Session, numero: int | None = None) -> str:
    """Construye un ticket único tipo `SC-2025-0042`."""
    if numero is None:
        ultimo = db.scalar(select(func.max(Solicitud.id))) or 0
        numero = int(ultimo) + 1
    return f"SC-2025-{numero:04d}"


def etiqueta_vigente(db: Session, solicitud_id: int) -> Etiqueta | None:
    """Devuelve la etiqueta vigente de una solicitud (o None)."""
    return db.scalars(
        select(Etiqueta).where(
            Etiqueta.solicitud_id == solicitud_id, Etiqueta.vigente.is_(True)
        )
    ).first()


def registrar_etiqueta(
    db: Session,
    solicitud: Solicitud,
    categoria: Categoria,
    prioridad: str,
    etiquetado_por: str,
) -> Etiqueta:
    """Registra una etiqueta nueva y desactiva la anterior (historial)."""
    if prioridad not in PRIORIDADES_VALIDAS:
        raise ValueError(f"Prioridad inválida: {prioridad}")

    anterior = etiqueta_vigente(db, solicitud.id)
    if anterior is not None:
        anterior.vigente = False

    nombre = etiquetado_por.strip() or "Equipo # 3"
    usuario = db.scalars(
        select(UsuarioEtiquetador).where(UsuarioEtiquetador.nombre == nombre)
    ).first()
    if usuario is None:
        usuario = UsuarioEtiquetador(nombre=nombre)
        db.add(usuario)

    etiqueta = Etiqueta(
        solicitud_id=solicitud.id,
        categoria_id=categoria.id,
        prioridad=prioridad,
        etiquetado_por=nombre,
        vigente=True,
    )
    db.add(etiqueta)
    db.flush()
    return etiqueta


def importar_solicitudes(
    db: Session, filas: Iterable[dict[str, str]], etiquetado_por: str = "Importación CSV"
) -> dict[str, Any]:
    """Importa filas (ID, Solicitud, Categoría, Prioridad) desde un CSV.

    Valida categoría y prioridad, evita duplicados por texto normalizado y
    reporta las filas inválidas sin abortar el proceso completo.
    """
    total = 0
    importadas = 0
    duplicadas = 0
    invalidas: list[dict[str, Any]] = []

    categorias = mapa_categorias(db)
    vistos = {
        texto
        for texto in db.scalars(select(Solicitud.texto_normalizado)).all()
        if texto
    }

    for indice, fila in enumerate(filas, start=1):
        total += 1
        texto = (fila.get("Solicitud") or fila.get("solicitud") or "").strip()
        categoria_txt = (fila.get("Categoría") or fila.get("Categoria") or fila.get("categoria") or "").strip()
        prioridad_txt = (fila.get("Prioridad") or fila.get("prioridad") or "").strip().upper()
        fila_id = fila.get("ID") or fila.get("id") or ""

        if len(texto) < 5:
            invalidas.append({"fila": indice, "id": fila_id, "motivo": "texto vacío o muy corto"})
            continue

        categoria = resolver_categoria(db, categoria_txt) if categoria_txt else None
        if categoria is None:
            invalidas.append(
                {"fila": indice, "id": fila_id, "motivo": f"categoría no reconocida: '{categoria_txt}'"}
            )
            continue

        if prioridad_txt not in PRIORIDADES_VALIDAS:
            invalidas.append(
                {"fila": indice, "id": fila_id, "motivo": f"prioridad inválida: '{prioridad_txt}'"}
            )
            continue

        clave_texto = normalizar(texto)
        if clave_texto in vistos:
            duplicadas += 1
            continue

        solicitud = Solicitud(
            ticket="",
            texto=texto,
            texto_normalizado=clave_texto,
            otb=(fila.get("OTB") or "Sin OTB").strip(),
            zona=(fila.get("Zona") or "Sin zona").strip(),
            estado="Sin asignar",
            origen="importado",
        )
        db.add(solicitud)
        db.flush()
        solicitud.ticket = generar_ticket(db, solicitud.id)

        registrar_etiqueta(db, solicitud, categoria, prioridad_txt, etiquetado_por)

        vistos.add(clave_texto)
        importadas += 1

    db.commit()
    return {
        "total_filas": total,
        "importadas": importadas,
        "duplicadas": duplicadas,
        "invalidas": invalidas,
    }


def estado_valido(estado: str) -> bool:
    """Comprueba si un estado está permitido."""
    return estado in ESTADOS_VALIDOS


def claves_validas() -> list[str]:
    """Devuelve las claves de categoría válidas."""
    return list(CLAVES_VALIDAS)
