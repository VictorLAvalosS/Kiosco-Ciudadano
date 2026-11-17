"""Demostración REAL de mejora del agente al aumentar los datos etiquetados.

Metodología (diseñada para la defensa y reproducible):
  * Se reserva SIEMPRE el mismo conjunto de prueba fijo (por grupos de
    casi-duplicados), de modo que todos los puntos de la curva son comparables.
  * El pool de entrenamiento se submuestrea de forma ESTRATIFICADA por categoría
    (misma proporción de cada clase) para las fracciones 10 %, 25 %, 50 %, 75 %
    y 100 %.
  * Cada fracción se repite con 5 semillas distintas y se reporta la MEDIA y la
    DESVIACIÓN ESTÁNDAR del F1 macro y de la accuracy: así se evita depender de
    una única partición afortunada.
  * Todos los resultados se guardan en la tabla `experimentos` de la base de datos
    y se pueden graficar en el panel (módulo Modelo).

Uso:
    python demo_mejora.py
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import select

from app.categorias import CATEGORIAS_SEED
from app.config import settings
from app.database import SessionLocal
from app.models import ConjuntoPruebaFijo, ExperimentoMejora
from app.servicio_modelo import etiquetas_vigentes
from ml import entrenamiento

# Fracciones del pool de entrenamiento que se evalúan.
FRACCIONES: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 1.00)
# Semillas distintas: permiten medir la variabilidad de cada punto de la curva.
SEMILLAS: tuple[int, ...] = (1, 7, 13, 21, 42)
# Algoritmo fijo para la demostración: mantiene comparables todos los puntos y
# evita recalcular la comparación de algoritmos en cada iteración.
ALGORITMO_DEMO = "Regresión Logística"


def _submuestra_estratificada(
    textos: list[str], etiquetas: list[str], fraccion: float, semilla: int
) -> tuple[list[str], list[str]]:
    """Submuestrea conservando la proporción de cada clase.

    Se toma `round(n_clase * fraccion)` ejemplos por clase (mínimo 2 por clase
    para que el entrenamiento sea posible) con una semilla fija.
    """
    if fraccion >= 1.0:
        return list(textos), list(etiquetas)

    rng = np.random.default_rng(semilla)
    indices_por_clase: dict[str, list[int]] = defaultdict(list)
    for indice, etiqueta in enumerate(etiquetas):
        indices_por_clase[etiqueta].append(indice)

    seleccion: list[int] = []
    for indices in indices_por_clase.values():
        arreglo = np.array(indices)
        rng.shuffle(arreglo)
        objetivo = max(2, int(round(len(arreglo) * fraccion)))
        seleccion.extend(arreglo[: min(objetivo, len(arreglo))].tolist())

    seleccion.sort()
    return [textos[i] for i in seleccion], [etiquetas[i] for i in seleccion]


def _ids_prueba(db: Any, registros: list[dict[str, Any]]) -> set[int]:
    """Ids del conjunto de prueba fijo vigente (lo reserva si aún no existe)."""
    ids = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())
    if ids:
        return {int(i) for i in ids}

    # Si aún no existe (dataset pequeño), reserva uno reproducible por grupos.
    from app.servicio_modelo import MINIMO_PARA_FIJO, regenerar_conjunto_prueba

    if len(registros) < MINIMO_PARA_FIJO:
        return set()
    ids, _ = regenerar_conjunto_prueba(db, registros)
    return ids


def main() -> int:
    """Ejecuta la demostración de mejora por volumen de datos etiquetados."""
    settings.validar()

    with SessionLocal() as db:
        registros = etiquetas_vigentes(db)
        if len(registros) < 20:
            print(
                "[AVISO] Se necesitan al menos 20 etiquetas vigentes para la demostración. "
                f"Hay {len(registros)}."
            )
            return 1

        ids_prueba = _ids_prueba(db, registros)
        pool = [r for r in registros if r["solicitud_id"] not in ids_prueba]
        prueba = [r for r in registros if r["solicitud_id"] in ids_prueba]

        if not prueba or not pool:
            print(
                "[AVISO] No se pudo reservar un conjunto de prueba fijo con grupos. "
                "Se necesitan más datos etiquetados."
            )
            return 1

        textos_pool = [r["texto"] for r in pool]
        etiquetas_pool = [r["categoria"] for r in pool]
        textos_prueba = [r["texto"] for r in prueba]
        etiquetas_prueba = [r["categoria"] for r in prueba]
        clases = [c["clave"] for c in CATEGORIAS_SEED]

        print("=" * 78)
        print("DEMOSTRACIÓN DE MEJORA POR VOLUMEN DE DATOS ETIQUETADOS")
        print("=" * 78)
        print(f"Etiquetas vigentes totales   : {len(registros)}")
        print(f"Conjunto de prueba fijo      : {len(textos_prueba)} (nunca se usa para entrenar)")
        print(f"Pool de entrenamiento        : {len(textos_pool)}")
        print(f"Repeticiones por fracción    : {len(SEMILLAS)} semillas {SEMILLAS}")
        print(f"Algoritmo de la demostración : {ALGORITMO_DEMO}")
        print("-" * 78)
        print(
            f"{'Fracción':>9} | {'n_train':>7} | {'accuracy (media±sd)':>22} | "
            f"{'F1 macro (media±sd)':>22}"
        )
        print("-" * 78)

        puntos: list[dict[str, Any]] = []
        for fraccion in FRACCIONES:
            accuracies: list[float] = []
            f1_scores: list[float] = []
            n_train = 0
            for semilla in SEMILLAS:
                X_sub, y_sub = _submuestra_estratificada(
                    textos_pool, etiquetas_pool, fraccion, semilla
                )
                n_train = len(X_sub)
                modelo, _ = entrenamiento.construir_clasificador(
                    X_sub, y_sub, comparacion={"ganador": ALGORITMO_DEMO}
                )
                metricas = entrenamiento.evaluar(modelo, textos_prueba, etiquetas_prueba, clases)
                accuracies.append(float(metricas["accuracy"]))
                f1_scores.append(float(metricas["f1_macro"]))

            punto = {
                "fraccion": fraccion,
                "n_entrenamiento": n_train,
                "accuracy_media": round(float(np.mean(accuracies)), 4),
                "accuracy_sd": round(float(np.std(accuracies)), 4),
                "f1_media": round(float(np.mean(f1_scores)), 4),
                "f1_sd": round(float(np.std(f1_scores)), 4),
                "repeticiones": len(SEMILLAS),
            }
            puntos.append(punto)
            print(
                f"{int(fraccion * 100):>8}% | {n_train:>7} | "
                f"{punto['accuracy_media']:>9.4f} ± {punto['accuracy_sd']:.4f}   | "
                f"{punto['f1_media']:>9.4f} ± {punto['f1_sd']:.4f}"
            )

        resultado: dict[str, Any] = {
            "metodologia": "submuestreo estratificado, repeticiones con semillas fijas",
            "algoritmo": ALGORITMO_DEMO,
            "semillas": list(SEMILLAS),
            "n_prueba": len(textos_prueba),
            "n_pool": len(textos_pool),
            "puntos": puntos,
        }

        db.add(
            ExperimentoMejora(
                tipo="mejora_volumen",
                n_total=len(registros),
                resultado=resultado,
            )
        )
        db.commit()

    print("-" * 78)
    print("Interpretación: al aumentar el porcentaje de etiquetas usadas en el")
    print("entrenamiento, el F1 macro y la accuracy (medidos sobre el MISMO conjunto")
    print("de prueba fijo) suben. La desviación estándar indica cuán estable es la")
    print("mejora frente a distintas particiones de entrenamiento.")
    print("Resultados guardados en la tabla `experimentos` de la base de datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
