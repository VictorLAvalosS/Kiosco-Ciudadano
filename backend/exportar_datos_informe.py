"""Genera el informe del agente (Markdown + JSON) leyendo TODO desde la BD.

Envoltorio de línea de comandos del servicio `app.servicio_informe.generar_informe`
(NO duplica lógica): produce exactamente el mismo informe que el botón
«Generar informe» de la interfaz y lo guarda en `backend/reporte/`.

Uso:
    python exportar_datos_informe.py
"""

from __future__ import annotations

import json

from app.config import settings
from app.database import SessionLocal
from app.servicio_informe import generar_informe


def main() -> int:
    """Genera el informe y lo escribe en `backend/reporte/`."""
    settings.validar()
    settings.reporte_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        resultado = generar_informe(db, {"generado_por": "exportar_datos_informe.py"})

    ruta_md = settings.reporte_dir / "datos_informe.md"
    ruta_json = settings.reporte_dir / "datos_informe.json"
    ruta_md.write_text(resultado["markdown"], encoding="utf-8")
    ruta_json.write_text(
        json.dumps(resultado["json"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Informe generado: {ruta_md}")
    print(f"JSON estructurado: {ruta_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
