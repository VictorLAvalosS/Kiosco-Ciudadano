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
    requiere_revision: bool = False
    umbral_confianza: float = 60.0
    umbral_margen: float = 15.0
    # Traza didáctica del agente (Fase A1): las 11 etapas reales del pipeline.
    traza: dict[str, Any] | None = None


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
    requiere_revision: bool = False
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
    # Evaluación ampliada (Fase 1-2).
    version_prueba: str = ""
    metodo_evaluacion: str = ""
    accuracy_prioridad: float = 0.0
    precision_prioridad: float = 0.0
    recall_prioridad: float = 0.0
    f1_prioridad: float = 0.0
    evaluacion: dict[str, Any] = Field(default_factory=dict)
    # Trazabilidad del entrenamiento (control de fuga de datos).
    n_ids_entrenamiento: int = 0
    valida_para_comparacion: bool = True
    motivo_invalidez: str = ""
    # Eficiencia medida realmente (Fase A3): tiempo de entrenamiento, tamaño del
    # binario serializado y latencia de predicción (media y p95).
    eficiencia: dict[str, Any] = Field(default_factory=dict)
    activo: bool


class EntrenarRequest(BaseModel):
    """Parámetros de reentrenamiento."""

    forzar: bool = False
    etiquetado_por: str = Field(default="", max_length=120)
    # Si es True, al terminar el reentrenamiento se genera y guarda un informe.
    generar_informe: bool = False


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


# ---------------------------------------------------------------------------
# Salud del sistema, calidad del dataset y acuerdo entre etiquetadores
# ---------------------------------------------------------------------------


class SaludOut(BaseModel):
    """Estado real del servicio: base de datos, modelo activo y umbrales."""

    estado: str
    servicio: str
    base_datos: str
    version_modelo: str | None = None
    n_etiquetas: int = 0
    umbral_confianza: float = 60.0
    umbral_margen: float = 15.0
    api_key_activa: bool = False


class CalidadDatasetOut(BaseModel):
    """Informe de calidad del dataset etiquetado (todo calculado con datos reales)."""

    total: int = 0
    por_categoria: dict[str, int] = Field(default_factory=dict)
    por_prioridad: dict[str, int] = Field(default_factory=dict)
    desbalance: dict[str, Any] = Field(default_factory=dict)
    longitud: dict[str, Any] = Field(default_factory=dict)
    duplicados_exactos: dict[str, Any] = Field(default_factory=dict)
    casi_duplicados: dict[str, Any] = Field(default_factory=dict)
    etiquetas_contradictorias: dict[str, Any] = Field(default_factory=dict)
    vocabulario_unico: int = 0


class AcuerdoOut(BaseModel):
    """Consistencia del etiquetado entre personas (kappa de Cohen)."""

    kappa_categoria: float | None = None
    kappa_prioridad: float | None = None
    puntuacion_observada_categoria: float | None = None
    puntuacion_observada_prioridad: float | None = None
    n_solicitudes_dobles: int = 0
    n_etiquetadores: int = 0
    discrepancias: list[dict[str, Any]] = Field(default_factory=list)
    mensaje: str = ""


# ---------------------------------------------------------------------------
# Informes del agente (Fase A5)
# ---------------------------------------------------------------------------


class InformeGenerarRequest(BaseModel):
    """Opciones para generar un informe del agente."""

    # Hasta 2 textos de ejemplo escritos por el usuario (opcional). Si se omiten,
    # se usan automáticamente uno de alta confianza y otro dudoso del conjunto de prueba.
    textos_ejemplo: list[str] = Field(default_factory=list, max_length=2)
    generado_por: str = Field(default="", max_length=120)
    # Si es True, la generación corre en segundo plano y el estado se consulta aparte.
    segundo_plano: bool = False


class InformeResumenOut(BaseModel):
    """Metadatos de un informe del agente (sin el contenido)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: datetime
    version_modelo: str
    generado_por: str
    estado: str
    error: str = ""


class InformeOut(InformeResumenOut):
    """Informe completo (Markdown + JSON estructurado)."""

    contenido_md: str
    contenido_json: dict[str, Any] = Field(default_factory=dict)


class InformeGenerarResponse(BaseModel):
    """Respuesta al solicitar la generación de un informe."""

    id: int
    estado: str
