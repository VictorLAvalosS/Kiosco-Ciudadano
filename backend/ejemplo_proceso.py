"""Ejemplo de proceso del agente (las 11 etapas) desde la línea de comandos.

Envoltorio delgado del servicio `app.servicio_informe` (NO duplica lógica):
usa `generar_informe` para obtener los datos reales de la base de datos y el
modelo activo, y `render_ejemplos_proceso` para renderizar únicamente la
sección de proceso paso a paso (la misma que muestra la interfaz en la Fase B).

Uso:
    python ejemplo_proceso.py
    python ejemplo_proceso.py "texto de ejemplo 1" "texto de ejemplo 2"

Sin argumentos, se eligen automáticamente una solicitud de ALTA confianza
(acertada, del conjunto de prueba) y otra DUDOSA (la de menor margen).
"""

from __future__ import annotations

import sys

from app.config import settings
from app.database import SessionLocal
from app.servicio_informe import generar_informe, render_ejemplos_proceso


def main(argv: list[str]) -> int:
    """Genera el Markdown del ejemplo de proceso y lo guarda en `backend/reporte/`."""
    settings.validar()
    settings.reporte_dir.mkdir(parents=True, exist_ok=True)

    textos = [texto for texto in argv if texto and texto.strip()][:2]

    with SessionLocal() as db:
        resultado = generar_informe(
            db,
            {"textos_ejemplo": textos, "generado_por": "ejemplo_proceso.py"},
        )

    markdown = render_ejemplos_proceso(resultado["json"])
    ruta = settings.reporte_dir / "ejemplo_proceso.md"
    ruta.write_text(markdown, encoding="utf-8")

    print(f"Ejemplo de proceso generado: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
