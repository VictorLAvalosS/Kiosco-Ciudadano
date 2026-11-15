"""Definición de las 8 categorías municipales fijas del sistema.

Estas categorías se insertan en la tabla `categorias` durante la migración inicial
y son la referencia (labels) del clasificador supervisado.
"""

from __future__ import annotations

# Orden oficial de las categorías. El índice define el `id` en la base de datos.
CATEGORIAS_SEED: list[dict[str, str]] = [
    {
        "clave": "alumbrado",
        "nombre": "Alumbrado público",
        "departamento": "Dirección de Alumbrado Público y Energía",
        "icono": "lightbulb",
    },
    {
        "clave": "limpieza",
        "nombre": "Limpieza y residuos sólidos",
        "departamento": "Dirección de Aseo Urbano y Gestión de Residuos",
        "icono": "trash",
    },
    {
        "clave": "calles",
        "nombre": "Calles y vías públicas",
        "departamento": "Dirección de Infraestructura Vial y Movilidad",
        "icono": "road",
    },
    {
        "clave": "agua",
        "nombre": "Agua potable y alcantarillado",
        "departamento": "Dirección de Obras Públicas y Redes de Agua",
        "icono": "droplet",
    },
    {
        "clave": "seguridad",
        "nombre": "Seguridad ciudadana",
        "departamento": "Dirección de Seguridad Ciudadana",
        "icono": "shield",
    },
    {
        "clave": "areas_verdes",
        "nombre": "Áreas verdes y espacios públicos",
        "departamento": "Dirección de Áreas Verdes y Medio Ambiente",
        "icono": "leaf",
    },
    {
        "clave": "drenaje",
        "nombre": "Drenaje y desagüe pluvial",
        "departamento": "Dirección de Drenaje y Alcantarillado Pluvial",
        "icono": "waves",
    },
    {
        "clave": "contaminacion",
        "nombre": "Contaminación ambiental",
        "departamento": "Dirección de Medio Ambiente y Control de Contaminación",
        "icono": "factory",
    },
]

# Listado de claves válidas (útil para validaciones rápidas en memoria).
CLAVES_VALIDAS: list[str] = [c["clave"] for c in CATEGORIAS_SEED]

# Prioridades admitidas por el sistema.
PRIORIDADES_VALIDAS: list[str] = ["ALTA", "MEDIA", "BAJA"]

# Estados admitidos para una solicitud.
ESTADOS_VALIDOS: list[str] = ["Sin asignar", "En proceso", "Asignado", "Resuelto"]
