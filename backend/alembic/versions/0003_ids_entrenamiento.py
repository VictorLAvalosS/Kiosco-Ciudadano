"""Trazabilidad del entrenamiento: ids usados y validez para comparación.

Corrige un error de evaluación (fuga de datos): algunas versiones se entrenaron
con ejemplos que después formaron parte del conjunto de prueba fijo, inflando sus
métricas. Se añade:

  * modelos: `ids_entrenamiento` (JSONB) con los ids de solicitud usados al
    entrenar, `valida_para_comparacion` (booleano) y `motivo_invalidez` (texto).

Una versión solo es comparable si `ids_entrenamiento` NO intersecta con el
conjunto de prueba fijo. Las que sí lo hacen quedan `valida_para_comparacion=false`
y no se muestran en la evolución ni pueden activarse sin forzar.

Revision ID: 0003_ids_entrenamiento
Revises: 0002_evaluacion
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_ids_entrenamiento"
down_revision: Union[str, None] = "0002_evaluacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "modelos",
        sa.Column(
            "ids_entrenamiento",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "modelos",
        sa.Column(
            "valida_para_comparacion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "modelos",
        sa.Column("motivo_invalidez", sa.String(length=200), nullable=False, server_default=""),
    )

    # Las versiones existentes no registraron sus ids de entrenamiento, por lo que
    # no se puede garantizar que sean disjuntas del conjunto de prueba: se marcan
    # como no comparables hasta que se reentrenen con la nueva trazabilidad.
    op.execute(
        "UPDATE modelos SET valida_para_comparacion = false, "
        "motivo_invalidez = 'sin ids de entrenamiento registrados (versión anterior a la corrección)' "
        "WHERE ids_entrenamiento = '[]'::jsonb;"
    )


def downgrade() -> None:
    op.drop_column("modelos", "motivo_invalidez")
    op.drop_column("modelos", "valida_para_comparacion")
    op.drop_column("modelos", "ids_entrenamiento")
