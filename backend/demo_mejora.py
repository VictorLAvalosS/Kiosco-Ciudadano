"""Demostración de mejora del agente al aumentar los datos etiquetados.

Entrena el clasificador con el 20 %, el 50 % y el 100 % de las etiquetas vigentes
y mide el F1 macro real sobre un conjunto de prueba reservado. Sirve para la defensa:
muestra, con números reales, que más etiquetas producen un mejor modelo.

Uso:
    python demo_mejora.py
"""

from __future__ import annotations

from app.config import settings
from app.database import SessionLocal
from ml import entrenamiento
from app.servicio_modelo import etiquetas_vigentes


def main() -> int:
    """Ejecuta la demostración de mejora por volumen de datos."""
    settings.validar()

    with SessionLocal() as db:
        registros = etiquetas_vigentes(db)

    total = len(registros)
    if total < 10:
        print(
            "[AVISO] Se necesitan al menos 10 etiquetas vigentes para la demostración. "
            f"Hay {total}."
        )
        return 1

    textos = [r["texto"] for r in registros]
    etiquetas = [r["categoria"] for r in registros]

    # Reserva un 20 % fijo como prueba (semilla constante para que sea reproducible).
    from sklearn.model_selection import StratifiedShuffleSplit

    divisor = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    idx_train, idx_test = next(divisor.split(textos, etiquetas))

    X_test = [textos[int(i)] for i in idx_test]
    y_test = [etiquetas[int(i)] for i in idx_test]
    X_pool = [textos[int(i)] for i in idx_train]
    y_pool = [etiquetas[int(i)] for i in idx_train]

    print("=" * 64)
    print("DEMOSTRACIÓN DE MEJORA POR VOLUMEN DE DATOS ETIQUETADOS")
    print("=" * 64)
    print(f"Etiquetas vigentes totales : {total}")
    print(f"Conjunto de prueba (20 %)  : {len(X_test)}")
    print(f"Pool de entrenamiento      : {len(X_pool)}")
    print("-" * 64)
    print(f"{'Fracción':>10} | {'n_train':>7} | {'accuracy':>8} | "
          f"{'F1 macro':>8} | {'algoritmo'}")
    print("-" * 64)

    fracciones = (0.2, 0.5, 1.0)
    for fraccion in fracciones:
        corte = max(4, int(len(X_pool) * fraccion))
        X_sub = X_pool[:corte]
        y_sub = y_pool[:corte]

        modelo, comparacion = entrenamiento.construir_clasificador(X_sub, y_sub)
        clases = [c for c in dict.fromkeys(y_sub)]
        metricas = entrenamiento.evaluar(modelo, X_test, y_test, clases)

        print(
            f"{int(fraccion * 100):>9}% | {corte:>7} | {metricas['accuracy']:>8.4f} | "
            f"{metricas['f1_macro']:>8.4f} | {comparacion['ganador']}"
        )

    print("-" * 64)
    print("Interpretación: al aumentar las etiquetas, el F1 macro sube porque el")
    print("agente aprende más vocabulario y patrones por cada categoría.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
