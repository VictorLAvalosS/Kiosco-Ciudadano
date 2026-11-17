"""Modelos ORM (SQLAlchemy 2.x) del sistema Kiosco Ciudadano.

Tablas:
  - categorias              → las 8 categorías municipales fijas.
  - solicitudes             → cada reclamo ciudadano y la predicción del modelo.
  - etiquetas               → etiqueta correcta (histórica) de una solicitud.
  - modelos                 → versiones entrenadas del agente (con el binario en BD).
  - conjunto_prueba_fijo    → ids reservados de prueba (comparabilidad entre versiones).
  - usuarios_etiquetadores  → personas del equipo que etiquetan.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Categoria(Base):
    """Categoría municipal a la que se deriva una solicitud."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    departamento: Mapped[str] = mapped_column(String(180), nullable=False)
    icono: Mapped[str] = mapped_column(String(40), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Categoria {self.id} {self.nombre}>"


class Solicitud(Base):
    """Solicitud ciudadana registrada (desde el kiosco, importación o panel)."""

    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    # Texto normalizado (sin tildes/mayúsculas) para detectar duplicados.
    texto_normalizado: Mapped[str] = mapped_column(String(700), nullable=False, index=True)
    otb: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    zona: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="Sin asignar")
    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="panel")

    # Resultado de la predicción del modelo activo (puede ser nulo si no había modelo).
    categoria_predicha_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id"), nullable=True
    )
    prioridad_predicha: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confianza: Mapped[float | None] = mapped_column(Float, nullable=True)
    probabilidades: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version_modelo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latencia_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Marca de revisión humana: confianza/margen por debajo de los umbrales.
    requiere_revision: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    categoria_predicha: Mapped[Categoria | None] = relationship(lazy="joined")
    etiquetas: Mapped[list["Etiqueta"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Solicitud {self.ticket} {self.estado}>"


class Etiqueta(Base):
    """Etiqueta correcta asignada por una persona del equipo.

    Se conserva el historial: al corregir, la etiqueta anterior se marca como
    `vigente=False` y se crea una nueva. Solo puede haber una vigente por solicitud.
    """

    __tablename__ = "etiquetas"
    __table_args__ = (
        # Índice único parcial: garantiza una sola etiqueta vigente por solicitud.
        Index(
            "uq_etiqueta_vigente_por_solicitud",
            "solicitud_id",
            unique=True,
            postgresql_where=text("vigente"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitudes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)
    prioridad: Mapped[str] = mapped_column(String(8), nullable=False)
    etiquetado_por: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    solicitud: Mapped[Solicitud] = relationship(back_populates="etiquetas")
    categoria: Mapped[Categoria] = relationship(lazy="joined")


class Modelo(Base):
    """Versión entrenada del agente. Guarda el binario joblib dentro de la BD."""

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    algoritmo: Mapped[str] = mapped_column(String(80), nullable=False)
    hiperparametros: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    n_entrenamiento: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_validacion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_prueba: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    precision_macro: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall_macro: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f1_macro: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    matriz_confusion: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metricas_por_clase: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    curva_aprendizaje: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    top_terminos: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # --- Evaluación ampliada (Fase 1-2) -----------------------------------
    # Versión del conjunto de prueba fijo usada (comparabilidad entre versiones).
    version_prueba: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # Método de evaluación ("conjunto_prueba_fijo" o "validacion_cruzada").
    metodo_evaluacion: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    # Métricas del clasificador de PRIORIDAD (ALTA / MEDIA / BAJA).
    accuracy_prioridad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    precision_prioridad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall_prioridad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f1_prioridad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Bloque JSONB con el resto de la evaluación: baselines, calibración,
    # curva cobertura-precisión, análisis de errores, matriz de prioridad,
    # casi-duplicados e hiperparámetros ajustados.
    evaluacion: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # --- Trazabilidad del entrenamiento (evita la fuga de datos) ----------
    # Ids de solicitud usados para entrenar esta versión. Permite comprobar que
    # el entrenamiento NO comparte ejemplos con el conjunto de prueba fijo.
    ids_entrenamiento: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Una versión solo es comparable si no usó ejemplos del conjunto de prueba.
    valida_para_comparacion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    # Motivo (texto) cuando la versión no es válida para comparación.
    motivo_invalidez: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Binario serializado con joblib: todo el equipo usa el mismo modelo desde la BD.
    modelo_binario: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Eficiencia medida realmente (Fase A3): tiempo de entrenamiento, tamaño del
    # binario serializado y latencia de predicción (media y p95) sobre la prueba.
    eficiencia: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<Modelo {self.version} f1={self.f1_macro:.3f} activo={self.activo}>"


class ConjuntoPruebaFijo(Base):
    """Ids de solicitud reservados para prueba. Nunca se usan para entrenar.

    El split es por GRUPOS de casi-duplicados: dos variantes de la misma frase
    nunca quedan a la vez en entrenamiento y prueba (evita fuga de datos).
    """

    __tablename__ = "conjunto_prueba_fijo"

    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitudes.id", ondelete="CASCADE"), primary_key=True
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Número de generación del conjunto de prueba (1, 2, ...).
    generacion: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Etiqueta de la versión del conjunto de prueba (p. ej. "prueba-g1").
    version_prueba: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # Identificador del grupo de casi-duplicados al que pertenece la solicitud.
    grupo: Mapped[str] = mapped_column(String(40), nullable=False, default="")


class ExperimentoMejora(Base):
    """Resultados de experimentos (p. ej. la demostración de mejora por volumen).

    Se guardan como JSONB para poder graficarlos en la interfaz y citarlos en el
    informe, sin depender de archivos locales.
    """

    __tablename__ = "experimentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Tipo de experimento (p. ej. "mejora_por_volumen").
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    n_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resultado: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class UsuarioEtiquetador(Base):
    """Persona del equipo que etiqueta solicitudes."""

    __tablename__ = "usuarios_etiquetadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Informe(Base):
    """Informe del agente (Markdown + JSON) persistido en la base de datos.

    Se guarda el contenido completo para poder consultarlo, descargarlo y
    versionarlo desde la interfaz, sin depender de archivos locales.
    """

    __tablename__ = "informes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Versión del modelo sobre la que se generó el informe.
    version_modelo: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    # Persona (o proceso) que solicitó el informe.
    generado_por: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Estado de la generación: en_proceso | completado | error.
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="completado")
    # Mensaje de error cuando la generación falla (vacío si todo fue bien).
    error: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    # Contenido del informe en Markdown y en JSON estructurado.
    contenido_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contenido_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Opciones usadas al generar (p. ej. los 2 textos de ejemplo del usuario).
    opciones: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
