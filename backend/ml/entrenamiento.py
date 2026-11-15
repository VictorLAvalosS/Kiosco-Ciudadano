"""Entrenamiento y evaluación de los clasificadores de categoría y prioridad.

Estrategia:
  * Vectorización TF-IDF con unigramas y bigramas.
  * Comparación de tres algoritmos con validación cruzada estratificada:
    Naive Bayes Multinomial, Regresión Logística y LinearSVC calibrado.
  * Selección del mejor algoritmo por F1 macro.
  * Con muy pocos datos (<30 por clase) se usa validación cruzada y se marca
    la bandera `datos_suficientes = False` para avisar en la interfaz.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, learning_curve
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml.preprocesamiento import texto_limpio

# Umbral por clase para considerar que hay "datos insuficientes".
MINIMO_POR_CLASE = 30


def _construir_vectorizador() -> TfidfVectorizer:
    """Vectorizador TF-IDF con unigramas y bigramas, listo para español normalizado."""
    return TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        token_pattern=r"(?u)\b\w\w+\b",
    )


def _folds_viables(etiquetas: list[str], max_folds: int = 5) -> int:
    """Calcula el número de folds estratificados posible según la clase menos frecuente."""
    conteo = Counter(etiquetas)
    minimo = min(conteo.values()) if conteo else 0
    return max(2, min(max_folds, minimo))


def candidatos(n_folds: int) -> dict[str, Callable[[], Any]]:
    """Fábricas de los tres clasificadores que se comparan."""
    return {
        "Naive Bayes Multinomial": lambda: MultinomialNB(),
        "Regresión Logística": lambda: LogisticRegression(
            max_iter=2000, class_weight="balanced", C=1.0
        ),
        "LinearSVC (calibrado)": lambda: CalibratedClassifierCV(
            LinearSVC(class_weight="balanced"), cv=max(2, n_folds)
        ),
    }


def _pipeline(clasificador: Any) -> Pipeline:
    """Encadena el vectorizador TF-IDF con el clasificador elegido."""
    return Pipeline([("tfidf", _construir_vectorizador()), ("clf", clasificador)])


def _hay_una_sola_clase(etiquetas: list[str]) -> bool:
    return len(set(etiquetas)) < 2


def comparar_algoritmos(
    textos: list[str], etiquetas: list[str]
) -> dict[str, Any]:
    """Compara los tres algoritmos con validación cruzada estratificada.

    Devuelve el nombre del ganador, su F1 macro medio y el detalle por algoritmo.
    """
    limpios = [texto_limpio(t) for t in textos]

    # Caso degenerado: una sola clase → clasificador trivial (evita errores de CV).
    if _hay_una_sola_clase(etiquetas):
        return {
            "ganador": "Clase única (most_frequent)",
            "detalle": {},
            "datos_suficientes": False,
        }

    folds = _folds_viables(etiquetas)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)

    detalle: dict[str, dict[str, float]] = {}
    mejor_nombre = ""
    mejor_f1 = -1.0

    for nombre, fabrica in candidatos(folds).items():
        try:
            modelo = _pipeline(fabrica())
            pred = cross_val_predict(modelo, limpios, etiquetas, cv=cv)
            f1 = float(f1_score(etiquetas, pred, average="macro", zero_division=0))
            detalle[nombre] = {
                "f1_macro": round(f1, 4),
                "accuracy": round(float(accuracy_score(etiquetas, pred)), 4),
                "precision_macro": round(
                    float(precision_score(etiquetas, pred, average="macro", zero_division=0)), 4
                ),
                "recall_macro": round(
                    float(recall_score(etiquetas, pred, average="macro", zero_division=0)), 4
                ),
            }
            if f1 > mejor_f1:
                mejor_f1 = f1
                mejor_nombre = nombre
        except Exception as error:  # pragma: no cover - depende de datos
            detalle[nombre] = {"f1_macro": 0.0, "error": str(error)}

    if not mejor_nombre:
        mejor_nombre = "Regresión Logística"

    minimo = min(Counter(etiquetas).values())
    return {
        "ganador": mejor_nombre,
        "detalle": detalle,
        "datos_suficientes": minimo >= MINIMO_POR_CLASE,
    }


def construir_clasificador(
    textos: list[str], etiquetas: list[str], nombre_algoritmo: str | None = None
) -> tuple[Pipeline, dict[str, Any]]:
    """Entrena el pipeline definitivo sobre todos los datos de entrenamiento.

    Devuelve el pipeline entrenado y un resumen de la comparación de algoritmos.
    """
    limpios = [texto_limpio(t) for t in textos]
    comparacion = comparar_algoritmos(textos, etiquetas)
    nombre = nombre_algoritmo or comparacion["ganador"]

    # Clasificador trivial cuando solo existe una clase.
    if _hay_una_sola_clase(etiquetas):
        modelo = _pipeline(DummyClassifier(strategy="most_frequent"))
        modelo.fit(limpios, etiquetas)
        return modelo, comparacion

    folds = _folds_viables(etiquetas)
    fabricas = candidatos(folds)
    if nombre not in fabricas:
        nombre = "Regresión Logística"

    modelo = _pipeline(fabricas[nombre]())
    modelo.fit(limpios, etiquetas)
    return modelo, comparacion


def evaluar(
    modelo: Pipeline, textos: list[str], etiquetas: list[str], clases_orden: list[str]
) -> dict[str, Any]:
    """Calcula métricas reales del modelo sobre un conjunto de evaluación."""
    limpios = [texto_limpio(t) for t in textos]
    if not limpios:
        return {
            "accuracy": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1_macro": 0.0,
            "matriz_confusion": [],
            "metricas_por_clase": {},
            "reporte": {},
        }

    pred = modelo.predict(limpios)
    etiquetas_presentes = sorted({*etiquetas, *pred})

    reporte = classification_report(
        etiquetas, pred, labels=etiquetas_presentes, output_dict=True, zero_division=0
    )

    metricas_por_clase: dict[str, dict[str, float]] = {}
    for clase in clases_orden:
        fila = reporte.get(clase, {})
        metricas_por_clase[clase] = {
            "precision": round(float(fila.get("precision", 0.0)), 4),
            "recall": round(float(fila.get("recall", 0.0)), 4),
            "f1": round(float(fila.get("f1-score", 0.0)), 4),
            "soporte": int(fila.get("support", 0)),
        }

    # Matriz de confusión ordenada según las clases oficiales (8x8 para categorías).
    etiquetas_matriz = [c for c in clases_orden if c in etiquetas_presentes]
    matriz: list[list[int]] = []
    if etiquetas_matriz:
        matriz = confusion_matrix(
            etiquetas, pred, labels=etiquetas_matriz
        ).tolist()

    return {
        "accuracy": round(float(accuracy_score(etiquetas, pred)), 4),
        "precision_macro": round(
            float(precision_score(etiquetas, pred, average="macro", zero_division=0)), 4
        ),
        "recall_macro": round(
            float(recall_score(etiquetas, pred, average="macro", zero_division=0)), 4
        ),
        "f1_macro": round(float(f1_score(etiquetas, pred, average="macro", zero_division=0)), 4),
        "matriz_confusion": matriz,
        "etiquetas_matriz": etiquetas_matriz,
        "metricas_por_clase": metricas_por_clase,
    }


def evaluar_por_validacion_cruzada(
    textos: list[str], etiquetas: list[str], clases_orden: list[str]
) -> dict[str, Any]:
    """Evalúa con validación cruzada cuando no hay suficientes datos para un test fijo."""
    limpios = [texto_limpio(t) for t in textos]
    if _hay_una_sola_clase(etiquetas) or len(limpios) < 4:
        return evaluar(_pipeline(DummyClassifier(strategy="most_frequent")).fit(limpios, etiquetas),
                       textos, etiquetas, clases_orden)

    folds = _folds_viables(etiquetas)
    comparacion = comparar_algoritmos(textos, etiquetas)
    fabricas = candidatos(folds)
    nombre = comparacion["ganador"] if comparacion["ganador"] in fabricas else "Regresión Logística"

    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    pred = cross_val_predict(_pipeline(fabricas[nombre]()), limpios, etiquetas, cv=cv)

    etiquetas_presentes = sorted({*etiquetas, *pred})
    reporte = classification_report(
        etiquetas, pred, labels=etiquetas_presentes, output_dict=True, zero_division=0
    )
    etiquetas_matriz = [c for c in clases_orden if c in etiquetas_presentes]

    return {
        "accuracy": round(float(accuracy_score(etiquetas, pred)), 4),
        "precision_macro": round(
            float(precision_score(etiquetas, pred, average="macro", zero_division=0)), 4
        ),
        "recall_macro": round(
            float(recall_score(etiquetas, pred, average="macro", zero_division=0)), 4
        ),
        "f1_macro": round(float(f1_score(etiquetas, pred, average="macro", zero_division=0)), 4),
        "matriz_confusion": (
            confusion_matrix(etiquetas, pred, labels=etiquetas_matriz).tolist()
            if etiquetas_matriz
            else []
        ),
        "etiquetas_matriz": etiquetas_matriz,
        "metricas_por_clase": {
            clase: {
                "precision": round(float(reporte.get(clase, {}).get("precision", 0.0)), 4),
                "recall": round(float(reporte.get(clase, {}).get("recall", 0.0)), 4),
                "f1": round(float(reporte.get(clase, {}).get("f1-score", 0.0)), 4),
                "soporte": int(reporte.get(clase, {}).get("support", 0)),
            }
            for clase in clases_orden
        },
        "metodo": "validacion_cruzada",
    }


def pares_confundidos(
    matriz: list[list[int]], etiquetas: list[str], limite: int = 5
) -> list[dict[str, Any]]:
    """Extrae los pares de clases más confundidos (fuera de la diagonal)."""
    pares: list[dict[str, Any]] = []
    for i, fila in enumerate(matriz):
        for j, valor in enumerate(fila):
            if i != j and valor > 0:
                pares.append(
                    {
                        "real": etiquetas[i],
                        "predicha": etiquetas[j],
                        "casos": int(valor),
                    }
                )
    pares.sort(key=lambda p: p["casos"], reverse=True)
    return pares[:limite]


def curva_de_aprendizaje(
    textos: list[str], etiquetas: list[str], puntos: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)
) -> dict[str, Any]:
    """Curva de aprendizaje real: F1 macro de validación al crecer los datos.

    Se calcula entrenando en subconjuntos crecientes y midiendo sobre el resto
    mediante particiones estratificadas.
    """
    limpios = [texto_limpio(t) for t in textos]
    resultado: dict[str, Any] = {"tamanos": [], "f1_validacion": [], "f1_entrenamiento": []}

    if _hay_una_sola_clase(etiquetas) or len(limpios) < 8:
        return resultado

    folds = _folds_viables(etiquetas)
    comparacion = comparar_algoritmos(textos, etiquetas)
    fabricas = candidatos(folds)
    nombre = comparacion["ganador"] if comparacion["ganador"] in fabricas else "Regresión Logística"

    try:
        tamanos, f1_train, f1_val = learning_curve(
            _pipeline(fabricas[nombre]()),
            limpios,
            etiquetas,
            train_sizes=list(puntos),
            cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=42),
            scoring="f1_macro",
            error_score=0.0,
        )
        resultado["tamanos"] = [int(t) for t in tamanos]
        resultado["f1_entrenamiento"] = [round(float(np.mean(f)), 4) for f in f1_train]
        resultado["f1_validacion"] = [round(float(np.mean(f)), 4) for f in f1_val]
    except Exception:  # pragma: no cover - depende de datos
        pass
    return resultado
