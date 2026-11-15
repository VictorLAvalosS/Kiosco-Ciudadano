"""Migración inicial: tablas del sistema, RLS y las 8 categorías fijas.

Revision ID: 0001_inicial
Revises:
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas sobre las que se activa Row Level Security.
TABLAS_RLS = [
    "categorias",
    "solicitudes",
    "etiquetas",
    "modelos",
    "conjunto_prueba_fijo",
    "usuarios_etiquetadores",
]

# Las 8 categorías municipales fijas (id explícito para conservar el orden oficial).
CATEGORIAS = [
    (1, "alumbrado", "Alumbrado público", "Dirección de Alumbrado Público y Energía", "lightbulb"),
    (2, "limpieza", "Limpieza y residuos sólidos", "Dirección de Aseo Urbano y Gestión de Residuos", "trash"),
    (3, "calles", "Calles y vías públicas", "Dirección de Infraestructura Vial y Movilidad", "road"),
    (4, "agua", "Agua potable y alcantarillado", "Dirección de Obras Públicas y Redes de Agua", "droplet"),
    (5, "seguridad", "Seguridad ciudadana", "Dirección de Seguridad Ciudadana", "shield"),
    (6, "areas_verdes", "Áreas verdes y espacios públicos", "Dirección de Áreas Verdes y Medio Ambiente", "leaf"),
    (7, "drenaje", "Drenaje y desagüe pluvial", "Dirección de Drenaje y Alcantarillado Pluvial", "waves"),
    (8, "contaminacion", "Contaminación ambiental", "Dirección de Medio Ambiente y Control de Contaminación", "factory"),
]


def upgrade() -> None:
    # --- categorias -------------------------------------------------------
    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(length=40), nullable=False, unique=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("departamento", sa.String(length=180), nullable=False),
        sa.Column("icono", sa.String(length=40), nullable=False),
    )

    # --- solicitudes ------------------------------------------------------
    op.create_table(
        "solicitudes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket", sa.String(length=32), nullable=False, unique=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("texto_normalizado", sa.String(length=700), nullable=False),
        sa.Column("otb", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("zona", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Sin asignar"),
        sa.Column("origen", sa.String(length=20), nullable=False, server_default="panel"),
        sa.Column("categoria_predicha_id", sa.Integer(), sa.ForeignKey("categorias.id"), nullable=True),
        sa.Column("prioridad_predicha", sa.String(length=8), nullable=True),
        sa.Column("confianza", sa.Float(), nullable=True),
        sa.Column("probabilidades", postgresql.JSONB(), nullable=True),
        sa.Column("version_modelo", sa.String(length=32), nullable=True),
        sa.Column("latencia_ms", sa.Float(), nullable=True),
    )
    op.create_index("ix_solicitudes_ticket", "solicitudes", ["ticket"])
    op.create_index("ix_solicitudes_texto_normalizado", "solicitudes", ["texto_normalizado"])

    # --- etiquetas --------------------------------------------------------
    op.create_table(
        "etiquetas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "solicitud_id",
            sa.Integer(),
            sa.ForeignKey("solicitudes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("categoria_id", sa.Integer(), sa.ForeignKey("categorias.id"), nullable=False),
        sa.Column("prioridad", sa.String(length=8), nullable=False),
        sa.Column("etiquetado_por", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_etiquetas_solicitud_id", "etiquetas", ["solicitud_id"])
    # Una sola etiqueta vigente por solicitud (índice único parcial).
    op.create_index(
        "uq_etiqueta_vigente_por_solicitud",
        "etiquetas",
        ["solicitud_id"],
        unique=True,
        postgresql_where=sa.text("vigente"),
    )

    # --- modelos ----------------------------------------------------------
    op.create_table(
        "modelos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(length=32), nullable=False, unique=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("algoritmo", sa.String(length=80), nullable=False),
        sa.Column("hiperparametros", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("n_entrenamiento", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_validacion", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_prueba", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("precision_macro", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recall_macro", sa.Float(), nullable=False, server_default="0"),
        sa.Column("f1_macro", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matriz_confusion", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metricas_por_clase", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("curva_aprendizaje", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("top_terminos", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("modelo_binario", sa.LargeBinary(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # --- conjunto_prueba_fijo --------------------------------------------
    op.create_table(
        "conjunto_prueba_fijo",
        sa.Column(
            "solicitud_id",
            sa.Integer(),
            sa.ForeignKey("solicitudes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- usuarios_etiquetadores ------------------------------------------
    op.create_table(
        "usuarios_etiquetadores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False, unique=True),
    )

    # --- Row Level Security ----------------------------------------------
    # El backend (rol propietario/servicio) es el único cliente. Al activar RLS
    # sin políticas, los roles públicos (anon/authenticated) quedan sin acceso.
    for tabla in TABLAS_RLS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;")

    # --- Datos iniciales: las 8 categorías --------------------------------
    tabla_categorias = sa.table(
        "categorias",
        sa.column("id", sa.Integer),
        sa.column("clave", sa.String),
        sa.column("nombre", sa.String),
        sa.column("departamento", sa.String),
        sa.column("icono", sa.String),
    )
    op.bulk_insert(
        tabla_categorias,
        [
            {"id": c[0], "clave": c[1], "nombre": c[2], "departamento": c[3], "icono": c[4]}
            for c in CATEGORIAS
        ],
    )

    # Ajusta la secuencia de ids para que los próximos inserts no colisionen.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('categorias', 'id'), "
        "(SELECT MAX(id) FROM categorias));"
    )


def downgrade() -> None:
    for tabla in reversed(TABLAS_RLS):
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY;")
    op.drop_table("usuarios_etiquetadores")
    op.drop_table("conjunto_prueba_fijo")
    op.drop_table("modelos")
    op.drop_index("uq_etiqueta_vigente_por_solicitud", table_name="etiquetas")
    op.drop_index("ix_etiquetas_solicitud_id", table_name="etiquetas")
    op.drop_table("etiquetas")
    op.drop_index("ix_solicitudes_texto_normalizado", table_name="solicitudes")
    op.drop_index("ix_solicitudes_ticket", table_name="solicitudes")
    op.drop_table("solicitudes")
    op.drop_table("categorias")
