"""Script de importación de etiquetas desde un CSV.

Uso:
    python importar_csv.py [ruta/al/archivo.csv]

Si no se indica una ruta, se usa `data/etiquetas_ejemplo.csv`.

El CSV debe tener las columnas: ID, Solicitud, Categoría, Prioridad.
Las filas inválidas se reportan sin abortar la importación completa.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.servicio_solicitudes import importar_solicitudes


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    """Lee el CSV tolerando el BOM de Excel/Google Sheets (utf-8-sig)."""
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        return [dict(fila) for fila in csv.DictReader(archivo)]


def main(argv: list[str]) -> int:
    """Punto de entrada del script.

    Uso:
        python importar_csv.py [ruta.csv] [--origen importado|prueba_externa]
    """
    settings.validar()

    argumentos = list(argv[1:])
    origen = "importado"
    if "--origen" in argumentos:
        indice = argumentos.index("--origen")
        origen = argumentos[indice + 1] if indice + 1 < len(argumentos) else "importado"
        argumentos = argumentos[:indice] + argumentos[indice + 2 :]

    if argumentos:
        ruta = Path(argumentos[0]).resolve()
    else:
        ruta = settings.data_dir / "etiquetas_ejemplo.csv"

    if not ruta.exists():
        print(f"[ERROR] No se encontró el archivo: {ruta}")
        return 1

    filas = leer_csv(ruta)
    print(f"[INFO] Archivo leído: {ruta} ({len(filas)} filas) · origen='{origen}'")

    with SessionLocal() as db:
        resultado = importar_solicitudes(
            db, filas, etiquetado_por="Importación CSV", origen=origen
        )

    print("[RESULTADO]")
    print(f"  Filas totales : {resultado['total_filas']}")
    print(f"  Importadas    : {resultado['importadas']}")
    print(f"  Duplicadas    : {resultado['duplicadas']}")
    print(f"  Inválidas     : {len(resultado['invalidas'])}")

    for invalida in resultado["invalidas"]:
        print(f"    - fila {invalida['fila']} (ID {invalida['id']}): {invalida['motivo']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
