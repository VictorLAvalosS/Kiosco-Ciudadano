"""Esquemas Pydantic (v2) para las peticiones y respuestas de la API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------


class CategoriaOut(BaseModel):
    """Categoría municipal expuesta por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    clave: str
    nombre: str
    departamento: str
    icono: str


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------


class PredecirResponse(BaseModel):
    """Resultado completo del pipeline NLP."""

    texto: str
    texto_normalizado: str
    tokens: list[str]
    tokens_originales: list[str]
    stopwords: int
    categoria: str
    categoria_nombre: str
    departamento: str
    icono: str
    prioridad: str
    confianza: float
    margen: float
    probabilidades: list[dict[str, Any]]
    probabilidades_prioridad: list[dict[str, Any]]
    contribuciones: list[dict[str, Any]]
    version_modelo: str
    algoritmo: str
    latencia_ms: float


# ---------------------------------------------------------------------------
# Solicitudes
# ---------------------------------------------------------------------------


class SolicitudCreate(BaseModel):
    """Cuerpo para crear una solicitud desde el kiosco."""

    texto: str = Field(min_length=5, max_length=700)
    otb: str = Field(default="", max_length=180)
    zona: str = Field(default="", max_length=180)
    origen: Literal["kiosco", "importado", "panel"] = "kiosco"


class EtiquetaOut(BaseModel):
    """Etiqueta vigente de una solicitud."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    categoria_id: int
    categoria_clave: str = ""
    categoria_nombre: str = ""
    prioridad: str
    etiquetado_por: str
    fecha: datetime
    vigente: bool


class SolicitudOut(BaseModel):
    """Solicitud con su predicción y su etiqueta vigente (si existe)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket: str
    texto: str
    otb: str
    zona: str
    fecha: datetime
    estado: str
    origen: str

    categoria_predicha_id: int | None = None
    categoria_predicha_clave: str | None = None
    categoria_predicha_nombre: str | None = None
    categoria_predicha_departamento: str | None = None
    categoria_predicha_icono: str | None = None
    prioridad_predicha: str | None = None
    confianza: float | None = None
    probabilidades: list[dict[str, Any]] | None = None
    version_modelo: str | None = None
    latencia_ms: float | None = None
    prediccion_detalle: PredecirResponse | None = None

    etiquetada: bool = False
    etiqueta: EtiquetaOut | None = None


class EstadoUpdate(BaseModel):
    """Cambio de estado de una solicitud."""

    estado: Literal["Sin asignar", "En proceso", "Asignado", "Resuelto"]


class AsignarRequest(BaseModel):
    """Asignación de una solicitud a una cuadrilla."""

    cuadrilla: str = Field(min_length=2, max_length=120)


class EtiquetaCreate(BaseModel):
    """Etiqueta correcta (categoría y prioridad) indicada por una persona."""

    categoria_clave: str
    prioridad: Literal["ALTA", "MEDIA", "BAJA"]
    etiquetado_por: str = Field(default="", max_length=120)


# ---------------------------------------------------------------------------
# Importación CSV
# ---------------------------------------------------------------------------


class ImportarResponse(BaseModel):
    """Resultado de una importación de etiquetas."""

    total_filas: int
    importadas: int
    duplicadas: int
    invalidas: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Modelo / entrenamiento
# ---------------------------------------------------------------------------


class ModeloOut(BaseModel):
    """Metadatos de una versión del modelo (sin el binario)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    fecha: datetime
    algoritmo: str
    hiperparametros: dict[str, Any]
    n_entrenamiento: int
    n_validacion: int
    n_prueba: int
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    matriz_confusion: dict[str, Any]
    metricas_por_clase: dict[str, Any]
    curva_aprendizaje: dict[str, Any]
    top_terminos: dict[str, Any]
    activo: bool


class EntrenarRequest(BaseModel):
    """Parámetros de reentrenamiento."""

    forzar: bool = False
    etiquetado_por: str = Field(default="", max_length=120)


class EntrenarResponse(BaseModel):
    """Resultado del reentrenamiento con comparación entre versiones."""

    activado: bool
    motivo: str
    version_nueva: ModeloOut | None = None
    version_anterior: ModeloOut | None = None
    comparacion_algoritmos: dict[str, Any] = Field(default_factory=dict)
    datos_suficientes: bool = True
    mensaje: str = ""


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------


class PredecirRequest(BaseModel):
    """Texto a clasificar sin persistir."""

    texto: str = Field(min_length=3, max_length=700)


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------


class EstadisticasOut(BaseModel):
    """Resumen del estado del dataset y del etiquetado."""

    total_solicitudes: int
    etiquetadas: int
    sin_etiquetar: int
    por_categoria: list[dict[str, Any]]
    por_etiquetador: list[dict[str, Any]]
    etiquetas_desde_ultimo_entrenamiento: int
    version_activa: str | None = None
    datos_suficientes: bool = False
    progreso_por_categoria: list[dict[str, Any]] = Field(default_factory=list)
