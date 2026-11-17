"""Evaluación ampliada: métricas de prioridad, calidad del dataset y experimentos.

Añade:
  * modelos: versión del conjunto de prueba, método de evaluación, métricas del
    clasificador de prioridad y un bloque JSONB con el resto de la evaluación.
  * conjunto_prueba_fijo: generación, versión y grupo (split por casi-duplicados).
  * solicitudes: marca de "requiere revisión humana".
  * tabla experimentos (demostración de mejora por volumen y otros estudios).

Revision ID: 0002_evaluacion
Revises: 0001_inicial
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_evaluacion"
down_revision: Union[str, None] = "0001_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- modelos: evaluación ampliada ------------------------------------
    op.add_column(
        "modelos",
        sa.Column("version_prueba", sa.String(length=16), nullable=False, server_default=""),
    )
    op.add_column(
        "modelos",
        sa.Column("metodo_evaluacion", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "modelos",
        sa.Column("accuracy_prioridad", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "modelos",
        sa.Column("precision_prioridad", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "modelos",
        sa.Column("recall_prioridad", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "modelos",
        sa.Column("f1_prioridad", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "modelos",
        sa.Column(
            "evaluacion",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # --- conjunto_prueba_fijo: generación y grupos -----------------------
    op.add_column(
        "conjunto_prueba_fijo",
        sa.Column("generacion", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "conjunto_prueba_fijo",
        sa.Column("version_prueba", sa.String(length=16), nullable=False, server_default=""),
    )
    op.add_column(
        "conjunto_prueba_fijo",
        sa.Column("grupo", sa.String(length=40), nullable=False, server_default=""),
    )

    # --- solicitudes: revisión humana ------------------------------------
    op.add_column(
        "solicitudes",
        sa.Column(
            "requiere_revision",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- tabla experimentos ----------------------------------------------
    op.create_table(
        "experimentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("n_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "resultado",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # Row Level Security: el backend es el único cliente (igual que el resto de tablas).
    op.execute("ALTER TABLE experimentos ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE experimentos DISABLE ROW LEVEL SECURITY;")
    op.drop_table("experimentos")

    op.drop_column("solicitudes", "requiere_revision")

    op.drop_column("conjunto_prueba_fijo", "grupo")
    op.drop_column("conjunto_prueba_fijo", "version_prueba")
    op.drop_column("conjunto_prueba_fijo", "generacion")

    op.drop_column("modelos", "evaluacion")
    op.drop_column("modelos", "f1_prioridad")
    op.drop_column("modelos", "recall_prioridad")
    op.drop_column("modelos", "precision_prioridad")
    op.drop_column("modelos", "accuracy_prioridad")
    op.drop_column("modelos", "metodo_evaluacion")
    op.drop_column("modelos", "version_prueba")
