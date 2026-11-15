"""Inferencia y explicabilidad del modelo entrenado.

Incluye:
  * Predicción de categoría y prioridad con probabilidades reales.
  * Cálculo del margen entre las dos clases más probables (aprendizaje activo).
  * Explicabilidad: términos con mayor contribución (coeficiente × tf-idf).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.pipeline import Pipeline

from ml.preprocesamiento import texto_limpio


def _obtener_probabilidades(modelo: Pipeline, textos_limpios: list[str]) -> np.ndarray:
    """Devuelve la matriz de probabilidades del pipeline (o una aproximación razonable)."""
    if hasattr(modelo, "predict_proba"):
        return np.asarray(modelo.predict_proba(textos_limpios))
    # Respaldo: one-hot sobre la predicción dura.
    clases = list(modelo.classes_)
    pred = modelo.predict(textos_limpios)
    matriz = np.zeros((len(pred), len(clases)))
    for fila, valor in enumerate(pred):
        matriz[fila, clases.index(valor)] = 1.0
    return matriz


def predecir_solicitud(
    modelo_categoria: Pipeline,
    modelo_prioridad: Pipeline,
    texto: str,
) -> dict[str, Any]:
    """Predice categoría y prioridad de un texto, con probabilidades y margen."""
    limpio = texto_limpio(texto)

    clases_cat = list(modelo_categoria.classes_)
    probs_cat = _obtener_probabilidades(modelo_categoria, [limpio])[0]
    orden_cat = np.argsort(probs_cat)[::-1]
    idx_ganador = int(orden_cat[0])
    categoria = clases_cat[idx_ganador]
    ranking_cat = [
        {"clase": clases_cat[int(i)], "probabilidad": round(float(probs_cat[int(i)]), 4)}
        for i in orden_cat
    ]
    margen = float(probs_cat[orden_cat[0]] - probs_cat[orden_cat[1]]) if len(orden_cat) > 1 else 1.0

    clases_pri = list(modelo_prioridad.classes_)
    probs_pri = _obtener_probabilidades(modelo_prioridad, [limpio])[0]
    orden_pri = np.argsort(probs_pri)[::-1]
    prioridad = clases_pri[int(orden_pri[0])]
    ranking_pri = [
        {"clase": clases_pri[int(i)], "probabilidad": round(float(probs_pri[int(i)]), 4)}
        for i in orden_pri
    ]

    return {
        "categoria": categoria,
        "confianza": round(float(probs_cat[idx_ganador]) * 100, 2),
        "margen": round(margen * 100, 2),
        "probabilidades": ranking_cat,
        "prioridad": prioridad,
        "confianza_prioridad": round(float(probs_pri[orden_pri[0]]) * 100, 2),
        "probabilidades_prioridad": ranking_pri,
        "texto_limpio": limpio,
    }


def _coeficientes_por_clase(modelo: Pipeline) -> tuple[np.ndarray, list[str]] | None:
    """Extrae la matriz de coeficientes (clases × términos) para modelos lineales."""
    vectorizador = modelo.named_steps["tfidf"]
    clasificador = modelo.named_steps["clf"]
    terminos = list(vectorizador.get_feature_names_out())

    if hasattr(clasificador, "coef_"):
        return np.asarray(clasificador.coef_), terminos

    # CalibratedClassifierCV: promedio de los coeficientes de los estimadores base.
    if hasattr(clasificador, "calibrated_classifiers_"):
        matrices = []
        for calibrado in clasificador.calibrated_classifiers_:
            estimador = getattr(calibrado, "estimator", None)
            if estimador is not None and hasattr(estimador, "coef_"):
                matrices.append(np.asarray(estimador.coef_))
        if matrices:
            return np.mean(matrices, axis=0), terminos

    # Naive Bayes: se usa el logaritmo de la probabilidad de cada término por clase.
    if hasattr(clasificador, "feature_log_prob_"):
        return np.asarray(clasificador.feature_log_prob_), terminos

    return None


def terminos_influyentes(modelo: Pipeline, top_n: int = 12) -> dict[str, list[dict[str, Any]]]:
    """Devuelve los n-gramas más influyentes de cada clase (explicabilidad global)."""
    datos = _coeficientes_por_clase(modelo)
    if datos is None:
        return {}
    coeficientes, terminos = datos
    clases = list(modelo.classes_)
    resultado: dict[str, list[dict[str, Any]]] = {}

    for indice, clase in enumerate(clases):
        if indice >= coeficientes.shape[0]:
            continue
        fila = coeficientes[indice]
        mejores = np.argsort(fila)[::-1][:top_n]
        resultado[str(clase)] = [
            {"termino": terminos[int(i)], "peso": round(float(fila[int(i)]), 4)}
            for i in mejores
        ]
    return resultado


def contribuciones_documento(
    modelo: Pipeline, texto: str, clase: str, top_n: int = 8
) -> list[dict[str, Any]]:
    """Términos que más aportaron a una predicción concreta (coeficiente × tf-idf)."""
    datos = _coeficientes_por_clase(modelo)
    if datos is None:
        return []
    coeficientes, terminos = datos
    clases = list(modelo.classes_)
    if clase not in clases:
        return []
    indice = clases.index(clase)

    vectorizador = modelo.named_steps["tfidf"]
    vector = vectorizador.transform([texto_limpio(texto)]).toarray()[0]

    aportes = vector * coeficientes[indice]
    mejores = np.argsort(aportes)[::-1][:top_n]
    return [
        {
            "termino": terminos[int(i)],
            "contribucion": round(float(aportes[int(i)]), 5),
            "tfidf": round(float(vector[int(i)]), 5),
        }
        for i in mejores
        if aportes[int(i)] > 0
    ]
