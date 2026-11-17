"""Configuración central del backend.

Lee todas las variables desde el archivo `.env` ubicado en `backend/`.
Ninguna credencial se escribe en el código: solo se leen de variables de entorno.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Directorio raíz del backend (backend/), dos niveles arriba de este archivo.
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Carga las variables definidas en backend/.env (si el archivo existe).
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Contenedor de configuración de la aplicación."""

    def __init__(self) -> None:
        # Cadena de conexión a PostgreSQL. Es obligatoria.
        self.database_url: str = os.getenv("DATABASE_URL", "").strip()

        # Orígenes permitidos por CORS (separados por coma).
        originos = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins: list[str] = [o.strip() for o in originos.split(",") if o.strip()]

        # Nombre del etiquetador por defecto cuando la petición no lo indique.
        self.etiquetador_por_defecto: str = os.getenv(
            "ETIQUETADOR_POR_DEFECTO", "Equipo # 3"
        ).strip()

        # Umbrales de "requiere revisión humana" (confianza y margen, en %).
        # Se aplican en la inferencia: por debajo de ellos la predicción se marca
        # como dudosa en lugar de forzar una categoría.
        self.umbral_confianza: float = float(os.getenv("UMBRAL_CONFIANZA", "60"))
        self.umbral_margen: float = float(os.getenv("UMBRAL_MARGEN", "15"))

        # Clave de API opcional para proteger los endpoints sensibles. Si queda
        # vacía, no se exige cabecera (útil en desarrollo y pruebas locales).
        self.api_key: str = os.getenv("API_KEY", "").strip()

        # Directorio de datos (CSV de ejemplo) y de modelos temporales.
        self.data_dir: Path = BASE_DIR / "data"

        # Directorio donde se generan los reportes del informe académico.
        self.reporte_dir: Path = BASE_DIR / "reporte"

    def validar(self) -> None:
        """Comprueba que la configuración mínima esté presente."""
        if not self.database_url:
            raise RuntimeError(
                "Falta la variable de entorno DATABASE_URL. "
                "Crea backend/.env a partir de backend/.env.example."
            )


settings = Settings()
