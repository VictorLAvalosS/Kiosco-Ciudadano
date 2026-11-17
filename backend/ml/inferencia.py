"""Inferencia y explicabilidad del modelo entrenado.

Incluye:
  * Predicción de categoría y prioridad con probabilidades reales.
  * Cálculo del margen entre las dos clases más probables (aprendizaje activo).
  * Explicabilidad: términos con mayor contribución (coeficiente × tf-idf).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from sklearn.pipeline import Pipeline

from ml.preprocesamiento import STOPWORDS, normalizar, texto_limpio, tokenizar

# Palabras originales (con tildes/mayúsculas) para mostrar el texto sin procesar.
_PALABRAS = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


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


# ---------------------------------------------------------------------------
# Traza didáctica del agente (Fase A1)
# ---------------------------------------------------------------------------


def puntajes_decision(modelo: Pipeline, limpio: str) -> list[dict[str, Any]]:
    """Puntajes de decisión s_c(x) = w_c·x + b_c por clase (Ecuación 4).

    Se usan los valores reales del modelo: `decision_function` del pipeline cuando
    está disponible (multiclase) o el producto coeficiente × vector TF-IDF como
    respaldo. El resultado llega ordenado de mayor a menor puntaje.
    """
    clases = list(modelo.classes_)
    puntajes: np.ndarray | None = None

    if hasattr(modelo, "decision_function"):
        try:
            valores = np.asarray(modelo.decision_function([limpio]))
            fila = valores[0] if valores.ndim > 1 else valores
            # En problemas binarios la salida es 1-D: se proyecta a las dos clases.
            if fila.ndim == 0 or len(fila) == 1:
                if len(clases) == 1:
                    puntajes = np.array([float(fila)])
                else:
                    puntajes = np.array([-float(fila[0]), float(fila[0])])
            else:
                puntajes = fila
        except Exception:  # pragma: no cover - respaldo según el modelo
            puntajes = None

    if puntajes is None:
        datos = _coeficientes_por_clase(modelo)
        if datos is None:
            return []
        coeficientes, _ = datos
        vector = modelo.named_steps["tfidf"].transform([limpio]).toarray()[0]
        puntajes = coeficientes @ vector

    orden = np.argsort(puntajes)[::-1]
    return [
        {"clase": clases[int(i)], "puntaje": round(float(puntajes[int(i)]), 5)}
        for i in orden
        if int(i) < len(clases)
    ]


def terminos_tfidf(modelo: Pipeline, limpio: str, top_n: int = 10) -> list[dict[str, Any]]:
    """Términos del documento con mayor peso TF-IDF y su valor real.

    Incluye además el término crudo (tf), su idf almacenado por el vectorizador y
    el peso TF-IDF, para poder explicar las Ecuaciones 1 y 2.
    """
    vectorizador = modelo.named_steps["tfidf"]
    matriz = vectorizador.transform([limpio]).toarray()[0]
    terminos = vectorizador.get_feature_names_out()
    ngramas = vectorizador.build_analyzer()(limpio)

    indices = [int(i) for i in np.argsort(matriz)[::-1] if matriz[int(i)] > 0][:top_n]
    salida: list[dict[str, Any]] = []
    for i in indices:
        tf = ngramas.count(str(terminos[i]))
        idf = float(vectorizador.idf_[i])
        salida.append(
            {
                "termino": str(terminos[i]),
                "tf": tf,
                "idf": round(idf, 5),
                "tfidf": round(float(matriz[i]), 5),
            }
        )
    return salida


def n_gramas(modelo: Pipeline, limpio: str) -> list[str]:
    """N-gramas realmente generados por el analizador del vectorizador TF-IDF."""
    return list(modelo.named_steps["tfidf"].build_analyzer()(limpio))


def _resumen_etapa(modelo: Pipeline, limpio: str, umbrales: dict[str, float]) -> dict[str, Any]:
    """Resumen de puntajes, probabilidades, margen y decisión para un clasificador."""
    probs = _obtener_probabilidades(modelo, [limpio])[0]
    clases = list(modelo.classes_)
    orden = np.argsort(probs)[::-1]
    margen = (
        float(probs[orden[0]] - probs[orden[1]]) * 100 if len(orden) > 1 else 100.0
    )
    confianza = float(probs[orden[0]]) * 100
    return {
        "clase": clases[int(orden[0])],
        "puntajes": puntajes_decision(modelo, limpio),
        "probabilidades": [
            {"clase": clases[int(i)], "probabilidad": round(float(probs[int(i)]), 4)}
            for i in orden
        ],
        "confianza": round(confianza, 2),
        "margen": round(margen, 2),
        "umbral_confianza": float(umbrales["confianza"]),
        "umbral_margen": float(umbrales["margen"]),
        "cumple_confianza": confianza >= float(umbrales["confianza"]),
        "cumple_margen": margen >= float(umbrales["margen"]),
    }


def construir_traza(
    modelo_categoria: Pipeline,
    modelo_prioridad: Pipeline,
    texto: str,
    umbrales: dict[str, float],
) -> dict[str, Any]:
    """Traza didáctica con los 11 pasos reales del agente (Fase A1).

    Pasos: (1) texto original, (2) normalizado, (3) tokens, (4) tokens sin
    stopwords, (5) n-gramas, (6) top TF-IDF, (7) puntajes por clase, (8)
    probabilidades calibradas, (9) margen, (10) comparación con umbrales y
    decisión final, (11) resumen equivalente para la prioridad.
    """
    limpio = texto_limpio(texto)
    tokens_normalizados = normalizar(texto).split()
    tokens_sin_stopwords = tokenizar(texto)
    eliminadas = sorted({t for t in tokens_normalizados if t in STOPWORDS})

    categoria = _resumen_etapa(modelo_categoria, limpio, umbrales)
    prioridad = _resumen_etapa(modelo_prioridad, limpio, umbrales)

    decision = "automatica" if (
        categoria["cumple_confianza"] and categoria["cumple_margen"]
    ) else "revision_humana"

    return {
        "texto_original": texto,
        "texto_normalizado": normalizar(texto),
        "tokens": tokens_normalizados,
        "tokens_sin_stopwords": tokens_sin_stopwords,
        "stopwords_eliminadas": eliminadas,
        "n_gramas": n_gramas(modelo_categoria, limpio),
        "terminos_tfidf": terminos_tfidf(modelo_categoria, limpio, top_n=10),
        "puntajes_categoria": categoria["puntajes"],
        "probabilidades_categoria": categoria["probabilidades"],
        "confianza_categoria": categoria["confianza"],
        "margen_categoria": categoria["margen"],
        "decision": {
            "confianza": categoria["confianza"],
            "umbral_confianza": categoria["umbral_confianza"],
            "cumple_confianza": categoria["cumple_confianza"],
            "margen": categoria["margen"],
            "umbral_margen": categoria["umbral_margen"],
            "cumple_margen": categoria["cumple_margen"],
            "resultado": decision,
            "categoria": categoria["clase"],
            "prioridad": prioridad["clase"],
        },
        "prioridad": {
            "clase": prioridad["clase"],
            "puntajes": prioridad["puntajes"],
            "probabilidades": prioridad["probabilidades"],
            "confianza": prioridad["confianza"],
            "margen": prioridad["margen"],
        },
    }
