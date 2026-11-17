"""Informes del agente y eficiencia medida por versión del modelo.

Añade:
  * modelos: `eficiencia` (JSONB) con tiempo de entrenamiento, tamaño del binario
    serializado y latencia de predicción (media y p95) sobre el conjunto de prueba.
  * tabla `informes`: contenido Markdown + JSON estructurado de cada informe del
    agente, con su estado (en_proceso/completado/error) y las opciones usadas.

Revision ID: 0004_informes_eficiencia
Revises: 0003_ids_entrenamiento
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_informes_eficiencia"
down_revision: Union[str, None] = "0003_ids_entrenamiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- modelos: eficiencia medida realmente -----------------------------
    op.add_column(
        "modelos",
        sa.Column(
            "eficiencia",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # --- tabla informes ---------------------------------------------------
    op.create_table(
        "informes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("version_modelo", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("generado_por", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="completado"),
        sa.Column("error", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("contenido_md", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "contenido_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "opciones",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # Row Level Security: el backend es el único cliente (igual que el resto de tablas).
    op.execute("ALTER TABLE informes ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE informes DISABLE ROW LEVEL SECURITY;")
    op.drop_table("informes")
    op.drop_column("modelos", "eficiencia")
