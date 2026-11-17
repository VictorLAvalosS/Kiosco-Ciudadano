"""Entrenamiento y evaluación de los clasificadores de categoría y prioridad.

Estrategia:
  * Vectorización TF-IDF con unigramas y bigramas (configurable).
  * Comparación de tres algoritmos con validación cruzada estratificada (y por
    GRUPOS cuando hay casi-duplicados, para no inflar las métricas).
  * Ajuste de hiperparámetros con GridSearchCV sobre particiones agrupadas.
  * Métricas reales, baselines, calibración de la confianza y análisis de errores.
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
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedGroupKFold,
    StratifiedKFold,
    cross_val_predict,
    learning_curve,
)
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml.preprocesamiento import texto_limpio

# Umbral por clase para considerar que hay "datos insuficientes".
MINIMO_POR_CLASE = 30

# Nombres canónicos de los algoritmos comparados.
ALGORITMOS = (
    "Naive Bayes Multinomial",
    "Regresión Logística",
    "LinearSVC (calibrado)",
)


# ---------------------------------------------------------------------------
# Construcción de pipelines e hiperparámetros
# ---------------------------------------------------------------------------


def _construir_vectorizador(
    ngram_range: tuple[int, int] = (1, 2), min_df: int = 1, sublinear_tf: bool = True
) -> TfidfVectorizer:
    """Vectorizador TF-IDF configurable, listo para español normalizado."""
    return TfidfVectorizer(
        ngram_range=ngram_range,
        sublinear_tf=sublinear_tf,
        min_df=min_df,
        token_pattern=r"(?u)\b\w\w+\b",
    )


def _clasificador(
    nombre: str,
    n_folds: int,
    parametros: dict[str, Any] | None = None,
    calibrar: bool = True,
) -> Any:
    """Devuelve un clasificador nuevo por nombre, aplicando hiperparámetros.

    `calibrar=False` deja el LinearSVC SIN la envoltura `CalibratedClassifierCV`.
    Se usa en las etapas que solo necesitan `predict` (comparación de algoritmos,
    rejilla de hiperparámetros y curva de aprendizaje): la calibración únicamente
    aporta probabilidades y, al anidar una validación cruzada interna, multiplica
    por `n_folds` el coste de esas etapas. El modelo FINAL sí se calibra.
    """
    parametros = parametros or {}
    if nombre == "Naive Bayes Multinomial":
        return MultinomialNB(alpha=float(parametros.get("alpha", 1.0)))
    if nombre == "LinearSVC (calibrado)":
        base = LinearSVC(class_weight="balanced", C=float(parametros.get("C", 1.0)))
        if not calibrar:
            return base
        return CalibratedClassifierCV(base, cv=max(2, n_folds))
    return LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        C=float(parametros.get("C", 1.0)),
    )


def _folds_viables(etiquetas: list[str], max_folds: int = 5, grupos: list[str] | None = None) -> int:
    """Calcula el número de folds posible según la clase (y el grupo) menos frecuente."""
    conteo = Counter(etiquetas)
    minimo = min(conteo.values()) if conteo else 0
    folds = max(2, min(max_folds, minimo))
    if grupos is not None:
        min_grupo = min(Counter(grupos).values()) if grupos else 0
        # Con grupos, cada fold necesita al menos un grupo por clase.
        folds = max(2, min(folds, min_grupo if min_grupo else folds))
    return folds


def _pipeline(clasificador: Any, ngram_range: tuple[int, int] = (1, 2), min_df: int = 1) -> Pipeline:
    """Encadena el vectorizador TF-IDF con el clasificador elegido."""
    return Pipeline(
        [
            ("tfidf", _construir_vectorizador(ngram_range, min_df)),
            ("clf", clasificador),
        ]
    )


def _hay_una_sola_clase(etiquetas: list[str]) -> bool:
    return len(set(etiquetas)) < 2


def candidatos(n_folds: int, calibrar: bool = True) -> dict[str, Callable[[], Any]]:
    """Fábricas de los tres clasificadores que se comparan (sin ajuste).

    `calibrar=False` se propaga a `_clasificador` (solo afecta al LinearSVC) y se
    usa cuando el resultado se evalúa con `predict` y no se necesitan probabilidades.
    """
    return {
        "Naive Bayes Multinomial": lambda: _clasificador(
            "Naive Bayes Multinomial", n_folds, calibrar=calibrar
        ),
        "Regresión Logística": lambda: _clasificador(
            "Regresión Logística", n_folds, calibrar=calibrar
        ),
        "LinearSVC (calibrado)": lambda: _clasificador(
            "LinearSVC (calibrado)", n_folds, calibrar=calibrar
        ),
    }


def _particionador(etiquetas: list[str], grupos: list[str] | None, n_folds: int) -> Any:
    """Devuelve el particionador de validación cruzada (agrupado si hay grupos)."""
    if grupos is not None:
        return StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=42)
    return StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)


# ---------------------------------------------------------------------------
# Comparación de algoritmos
# ---------------------------------------------------------------------------


def comparar_algoritmos(
    textos: list[str], etiquetas: list[str], grupos: list[str] | None = None
) -> dict[str, Any]:
    """Compara los tres algoritmos con validación cruzada (agrupada si procede)."""
    limpios = [texto_limpio(t) for t in textos]

    if _hay_una_sola_clase(etiquetas):
        return {
            "ganador": "Clase única (most_frequent)",
            "detalle": {},
            "datos_suficientes": False,
        }

    folds = _folds_viables(etiquetas, grupos=grupos)
    cv = _particionador(etiquetas, grupos, folds)

    detalle: dict[str, dict[str, float]] = {}
    mejor_nombre = ""
    mejor_f1 = -1.0

    for nombre, fabrica in candidatos(folds, calibrar=False).items():
        try:
            modelo = _pipeline(fabrica())
            if grupos is not None:
                pred = cross_val_predict(modelo, limpios, etiquetas, cv=cv, groups=grupos)
            else:
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
        "metodo": "validacion_cruzada_agrupada" if grupos is not None else "validacion_cruzada",
    }


# ---------------------------------------------------------------------------
# Ajuste de hiperparámetros (GridSearchCV agrupado)
# ---------------------------------------------------------------------------

# Rejillas por algoritmo: C (LogReg/LinearSVC), alpha (Naive Bayes) y parámetros
# de la vectorización TF-IDF (ngram_range y min_df).
# La búsqueda se hace sobre el LinearSVC SIN calibrar (clave `clf__C`): el F1 macro
# se calcula con `predict`, por lo que la calibración (y su validación cruzada
# interna) solo encarecería la búsqueda sin cambiar el criterio de selección.
_REJILLAS: dict[str, dict[str, list[Any]]] = {
    "Naive Bayes Multinomial": {"clf__alpha": [0.1, 0.5, 1.0]},
    "Regresión Logística": {"clf__C": [0.5, 1.0, 2.0, 5.0]},
    "LinearSVC (calibrado)": {"clf__C": [0.5, 1.0, 2.0, 5.0]},
}
_GRID_VECTORIZADOR: dict[str, list[Any]] = {
    "tfidf__ngram_range": [(1, 1), (1, 2)],
    "tfidf__min_df": [1, 2],
}


def ajustar_hiperparametros(
    textos: list[str], etiquetas: list[str], grupos: list[str] | None = None
) -> dict[str, Any]:
    """Busca los mejores hiperparámetros con GridSearchCV (particiones agrupadas).

    Devuelve la mejor configuración, su F1 macro y una tabla con los resultados
    más relevantes. Todo se calcula con datos reales.
    """
    vacio: dict[str, Any] = {"mejor": None, "f1_macro": 0.0, "tabla": []}
    if _hay_una_sola_clase(etiquetas) or len(textos) < 12:
        return vacio

    limpios = [texto_limpio(t) for t in textos]
    folds = _folds_viables(etiquetas, max_folds=4, grupos=grupos)
    cv = _particionador(etiquetas, grupos, folds)

    tabla: list[dict[str, Any]] = []
    mejor: dict[str, Any] | None = None
    mejor_f1 = -1.0

    for nombre, rejilla in _REJILLAS.items():
        grid = {**_GRID_VECTORIZADOR, **rejilla}
        # Se busca con el clasificador SIN calibrar (solo se evalúa con `predict`).
        pipeline = _pipeline(_clasificador(nombre, folds, calibrar=False))
        try:
            busqueda = GridSearchCV(
                # n_jobs=1 (un solo proceso): en Windows el multiproceso de joblib
                # reimporta scikit-learn en cada worker y resulta MÁS LENTO que
                # seguir en el proceso principal (medido para esta rejilla).
                pipeline, grid, scoring="f1_macro", cv=cv, n_jobs=1, error_score=0.0
            )
            if grupos is not None:
                busqueda.fit(limpios, etiquetas, groups=grupos)
            else:
                busqueda.fit(limpios, etiquetas)
        except Exception as error:  # pragma: no cover - depende de datos
            tabla.append({"algoritmo": nombre, "error": str(error)})
            continue

        for parametros, puntaje in zip(
            busqueda.cv_results_["params"], busqueda.cv_results_["mean_test_score"]
        ):
            tabla.append(
                {
                    "algoritmo": nombre,
                    "ngram_range": list(parametros["tfidf__ngram_range"]),
                    "min_df": int(parametros["tfidf__min_df"]),
                    "parametros": {
                        clave.split("__")[-1]: valor
                        for clave, valor in parametros.items()
                        if clave not in _GRID_VECTORIZADOR
                    },
                    "f1_macro": round(float(puntaje), 4),
                }
            )

        if float(busqueda.best_score_) > mejor_f1:
            mejor_f1 = float(busqueda.best_score_)
            mejor = {
                "algoritmo": nombre,
                "ngram_range": list(busqueda.best_params_["tfidf__ngram_range"]),
                "min_df": int(busqueda.best_params_["tfidf__min_df"]),
                "parametros": {
                    clave.split("__")[-1]: valor
                    for clave, valor in busqueda.best_params_.items()
                    if clave not in _GRID_VECTORIZADOR
                },
            }

    tabla.sort(key=lambda fila: fila.get("f1_macro", 0.0), reverse=True)
    return {"mejor": mejor, "f1_macro": round(mejor_f1, 4) if mejor else 0.0, "tabla": tabla[:12]}


def _pipeline_desde_config(config: dict[str, Any], n_folds: int) -> Pipeline:
    """Construye el pipeline final a partir de la mejor configuración ajustada."""
    ngram = tuple(config.get("ngram_range", (1, 2)))  # type: ignore[arg-type]
    return _pipeline(
        _clasificador(config["algoritmo"], n_folds, config.get("parametros")),
        ngram_range=ngram,  # type: ignore[arg-type]
        min_df=int(config.get("min_df", 1)),
    )


# ---------------------------------------------------------------------------
# Entrenamiento del clasificador final
# ---------------------------------------------------------------------------


def construir_clasificador(
    textos: list[str],
    etiquetas: list[str],
    nombre_algoritmo: str | None = None,
    comparacion: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[Pipeline, dict[str, Any]]:
    """Entrena el pipeline definitivo sobre todos los datos de entrenamiento.

    `comparacion` permite reutilizar el resultado de `comparar_algoritmos` ya
    calculado (evita repetir la validación cruzada tres veces por entrenamiento).
    `config` permite usar la mejor configuración hallada por GridSearchCV.
    """
    limpios = [texto_limpio(t) for t in textos]
    if comparacion is None:
        comparacion = comparar_algoritmos(textos, etiquetas)

    # Clasificador trivial cuando solo existe una clase.
    if _hay_una_sola_clase(etiquetas):
        modelo = _pipeline(DummyClassifier(strategy="most_frequent"))
        modelo.fit(limpios, etiquetas)
        return modelo, comparacion

    folds = _folds_viables(etiquetas)
    if config:
        modelo = _pipeline_desde_config(config, folds)
        modelo.fit(limpios, etiquetas)
        return modelo, comparacion

    nombre = nombre_algoritmo or comparacion["ganador"]
    fabricas = candidatos(folds)
    if nombre not in fabricas:
        nombre = "Regresión Logística"

    modelo = _pipeline(fabricas[nombre]())
    modelo.fit(limpios, etiquetas)
    return modelo, comparacion


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


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
            "etiquetas_matriz": [],
            "metricas_por_clase": {},
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

    etiquetas_matriz = [c for c in clases_orden if c in etiquetas_presentes]
    matriz: list[list[int]] = []
    if etiquetas_matriz:
        matriz = confusion_matrix(etiquetas, pred, labels=etiquetas_matriz).tolist()

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
    textos: list[str],
    etiquetas: list[str],
    clases_orden: list[str],
    nombre_algoritmo: str | None = None,
    comparacion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evalúa con validación cruzada cuando no hay suficientes datos para test fijo."""
    limpios = [texto_limpio(t) for t in textos]
    if _hay_una_sola_clase(etiquetas) or len(limpios) < 4:
        return evaluar(
            _pipeline(DummyClassifier(strategy="most_frequent")).fit(limpios, etiquetas),
            textos,
            etiquetas,
            clases_orden,
        )

    if comparacion is None:
        comparacion = comparar_algoritmos(textos, etiquetas)
    folds = _folds_viables(etiquetas)
    fabricas = candidatos(folds)
    nombre = nombre_algoritmo or comparacion["ganador"]
    if nombre not in fabricas:
        nombre = "Regresión Logística"

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


def baselines(
    y_train: list[str],
    textos_test: list[str],
    y_test: list[str],
    clases_orden: list[str],
    random_state: int = 42,
) -> dict[str, Any]:
    """Desempeño de dos clasificadores triviales sobre el mismo conjunto de prueba.

    (a) Clase mayoritaria: siempre predice la clase más frecuente del entrenamiento.
    (b) Aleatorio estratificado: muestrea etiquetas según la distribución del
        entrenamiento (misma proporción de clases).
    Sirven para demostrar que el agente supera ampliamente el azar.
    """
    if not y_test:
        return {}

    conteo = Counter(y_train) or Counter(y_test)
    clases = [c for c in clases_orden if c in conteo] or list(conteo.keys())
    mayoritaria = conteo.most_common(1)[0][0]
    pred_mayoritaria = [mayoritaria] * len(y_test)

    rng = np.random.default_rng(random_state)
    probabilidades = np.array([conteo.get(c, 0) for c in clases], dtype=float)
    probabilidades = probabilidades / probabilidades.sum() if probabilidades.sum() else None
    pred_aleatoria = list(rng.choice(clases, size=len(y_test), p=probabilidades))

    def _metricas(pred: list[str]) -> dict[str, float]:
        return {
            "accuracy": round(float(accuracy_score(y_test, pred)), 4),
            "precision_macro": round(
                float(precision_score(y_test, pred, labels=clases, average="macro", zero_division=0)),
                4,
            ),
            "recall_macro": round(
                float(recall_score(y_test, pred, labels=clases, average="macro", zero_division=0)),
                4,
            ),
            "f1_macro": round(
                float(f1_score(y_test, pred, labels=clases, average="macro", zero_division=0)), 4
            ),
        }

    return {
        "mayoritaria": {**_metricas(pred_mayoritaria), "clase": mayoritaria},
        "aleatoria_estratificada": _metricas(pred_aleatoria),
        "n_prueba": len(y_test),
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


# ---------------------------------------------------------------------------
# Calibración de la confianza
# ---------------------------------------------------------------------------


def calibracion_confianza(
    modelo: Pipeline, textos: list[str], etiquetas: list[str]
) -> dict[str, Any]:
    """Fiabilidad de la confianza del modelo (tabla + Brier + ECE).

    Si "70 % de confianza" significa aproximadamente 70 % de acierto, la columna
    `exactitud` de la tabla debe parecerse a `confianza_media` en cada rango.
    """
    limpios = [texto_limpio(t) for t in textos]
    if not limpios or not hasattr(modelo, "predict_proba"):
        return {"tabla": [], "brier": None, "ece": None, "n": 0}

    probabilidades = np.asarray(modelo.predict_proba(limpios))
    clases = list(modelo.classes_)
    indice_clase = {clase: i for i, clase in enumerate(clases)}

    indices = probabilidades.argmax(axis=1)
    pred = [clases[int(i)] for i in indices]
    confianza = probabilidades.max(axis=1)
    acierto = np.array([1.0 if p == y else 0.0 for p, y in zip(pred, etiquetas)])

    rangos = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)]
    tabla: list[dict[str, Any]] = []
    for bajo, alto in rangos:
        mascara = (confianza >= bajo) & (confianza < alto)
        n = int(mascara.sum())
        if n == 0:
            tabla.append(
                {"rango": [bajo, min(alto, 1.0)], "n": 0, "confianza_media": None, "exactitud": None}
            )
            continue
        tabla.append(
            {
                "rango": [bajo, min(alto, 1.0)],
                "n": n,
                "confianza_media": round(float(confianza[mascara].mean()), 4),
                "exactitud": round(float(acierto[mascara].mean()), 4),
            }
        )

    # Brier multiclase: media de la suma de errores cuadráticos por clase.
    objetivo = np.zeros_like(probabilidades)
    for fila, etiqueta in enumerate(etiquetas):
        if etiqueta in indice_clase:
            objetivo[fila, indice_clase[etiqueta]] = 1.0
    brier = float(((probabilidades - objetivo) ** 2).sum(axis=1).mean())

    # ECE: error de calibración esperado ponderado por el tamaño de cada rango.
    total = len(confianza)
    ece = 0.0
    for fila in tabla:
        if fila["n"]:
            ece += fila["n"] / total * abs(fila["exactitud"] - fila["confianza_media"])

    return {
        "tabla": tabla,
        "brier": round(brier, 4),
        "ece": round(float(ece), 4),
        "n": total,
    }


def curva_cobertura_precision(
    modelo: Pipeline,
    textos: list[str],
    etiquetas: list[str],
    umbrales: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Cobertura vs. precisión al variar el umbral de confianza.

    Permite elegir, con datos, el umbral de "requiere revisión humana": a mayor
    umbral, menor cobertura (menos casos se aceptan) pero mayor precisión.
    """
    limpios = [texto_limpio(t) for t in textos]
    if not limpios or not hasattr(modelo, "predict_proba"):
        return []

    umbrales = umbrales or [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    probabilidades = np.asarray(modelo.predict_proba(limpios))
    clases = list(modelo.classes_)
    pred = [clases[int(i)] for i in probabilidades.argmax(axis=1)]
    confianza = probabilidades.max(axis=1)
    acierto = np.array([1.0 if p == y else 0.0 for p, y in zip(pred, etiquetas)])
    total = len(confianza)

    puntos: list[dict[str, Any]] = []
    for umbral in umbrales:
        mascara = confianza >= umbral
        n = int(mascara.sum())
        puntos.append(
            {
                "umbral": umbral,
                "n": n,
                "cobertura": round(n / total, 4) if total else 0.0,
                "precision": round(float(acierto[mascara].mean()), 4) if n else None,
            }
        )
    return puntos


def errores_clasificacion(
    modelo: Pipeline, textos: list[str], etiquetas: list[str], limite: int = 25
) -> list[dict[str, Any]]:
    """Casos mal clasificados del conjunto de prueba (con su confianza real)."""
    limpios = [texto_limpio(t) for t in textos]
    if not limpios:
        return []

    pred = list(modelo.predict(limpios))
    if hasattr(modelo, "predict_proba"):
        probabilidades = np.asarray(modelo.predict_proba(limpios))
        confianzas = probabilidades.max(axis=1)
    else:
        confianzas = np.ones(len(pred))

    errores = [
        {
            "texto": texto,
            "real": real,
            "predicha": predicha,
            "confianza": round(float(confianza), 4),
        }
        for texto, real, predicha, confianza in zip(textos, etiquetas, pred, confianzas)
        if real != predicha
    ]
    errores.sort(key=lambda error: error["confianza"], reverse=True)
    return errores[:limite]


def curva_de_aprendizaje(
    textos: list[str],
    etiquetas: list[str],
    nombre_algoritmo: str | None = None,
    comparacion: dict[str, Any] | None = None,
    puntos: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0),
) -> dict[str, Any]:
    """Curva de aprendizaje real: F1 macro de validación al crecer los datos."""
    limpios = [texto_limpio(t) for t in textos]
    resultado: dict[str, Any] = {"tamanos": [], "f1_validacion": [], "f1_entrenamiento": []}

    if _hay_una_sola_clase(etiquetas) or len(limpios) < 8:
        return resultado

    if comparacion is None:
        comparacion = comparar_algoritmos(textos, etiquetas)
    folds = _folds_viables(etiquetas)
    # La curva solo necesita `predict` (F1 macro): basta el clasificador sin calibrar.
    fabricas = candidatos(folds, calibrar=False)
    nombre = nombre_algoritmo or comparacion["ganador"]
    if nombre not in fabricas:
        nombre = "Regresión Logística"

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
