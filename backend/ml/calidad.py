"""Calidad del dataset y detección de casi-duplicados.

Motivación (informe y defensa):
  * Si dos variantes de la misma frase ("el foco de la esquina está quemado" y
    "el foco de la esquina lleva tres noches quemado") caen una en entrenamiento
    y otra en prueba, el modelo las "reconoce" y las métricas salen infladas
    (fuga de datos / leakage). Para evitarlo se agrupan los textos casi iguales
    (similitud coseno TF-IDF >= umbral) y el split se hace por GRUPOS.
  * Además se auditan otras señales de mala calidad: desbalance de clases,
    duplicados exactos, etiquetas contradictorias y tamaño del vocabulario.

Todas las cifras que devuelve este módulo se calculan sobre datos reales.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ml.preprocesamiento import normalizar, texto_limpio, tokenizar

# Umbral por defecto de similitud coseno para considerar dos textos "casi iguales".
UMBRAL_CASI_DUPLICADO = 0.85

# Nº máximo de ejemplos que se listan por grupo en el informe (evita respuestas enormes).
MAX_EJEMPLOS_GRUPO = 3


def _vectorizar(textos: list[str]) -> np.ndarray:
    """Vectoriza los textos con TF-IDF para poder compararlos por similitud coseno."""
    limpios = [texto_limpio(t) for t in textos]
    vectorizador = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        token_pattern=r"(?u)\b\w\w+\b",
    )
    matriz = vectorizador.fit_transform(limpios)
    return matriz


def agrupar_casi_duplicados(
    textos: list[str], umbral: float = UMBRAL_CASI_DUPLICADO
) -> list[str]:
    """Devuelve, para cada texto, la etiqueta del grupo de casi-duplicados.

    Dos textos quedan en el mismo grupo si su similitud coseno TF-IDF es mayor o
    igual al umbral (se agrupa de forma transitiva con union-find). Cada texto
    sin vecinos forma su propio grupo (tamaño 1).
    """
    n = len(textos)
    if n == 0:
        return []

    # Union-find simple con compresión de caminos.
    padres = list(range(n))

    def encontrar(x: int) -> int:
        while padres[x] != x:
            padres[x] = padres[padres[x]]
            x = padres[x]
        return x

    def unir(a: int, b: int) -> None:
        ra, rb = encontrar(a), encontrar(b)
        if ra != rb:
            padres[rb] = ra

    try:
        matriz = _vectorizar(textos)
        similitud = cosine_similarity(matriz)
    except ValueError:
        # Si no hay vocabulario (textos vacíos) cada texto es su propio grupo.
        return [f"g{i}" for i in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            if similitud[i, j] >= umbral:
                unir(i, j)

    # Traduce raíces a etiquetas legibles g0, g1, ...
    etiquetas: dict[int, str] = {}
    salida: list[str] = []
    for i in range(n):
        raiz = encontrar(i)
        if raiz not in etiquetas:
            etiquetas[raiz] = f"g{len(etiquetas)}"
        salida.append(etiquetas[raiz])
    return salida


def detectar_casi_duplicados(
    textos: list[str], umbral: float = UMBRAL_CASI_DUPLICADO
) -> dict[str, Any]:
    """Resume los grupos de casi-duplicados encontrados en un conjunto de textos."""
    etiquetas = agrupar_casi_duplicados(textos, umbral)
    if not etiquetas:
        return {
            "umbral": umbral,
            "n_grupos": 0,
            "n_casi_duplicados": 0,
            "grupos": [],
        }

    miembros: dict[str, list[int]] = defaultdict(list)
    for indice, grupo in enumerate(etiquetas):
        miembros[grupo].append(indice)

    grupos = [
        (grupo, indices) for grupo, indices in miembros.items() if len(indices) > 1
    ]
    grupos.sort(key=lambda par: len(par[1]), reverse=True)

    detalles = [
        {
            "grupo": grupo,
            "n": len(indices),
            "ejemplos": [textos[i][:160] for i in indices[:MAX_EJEMPLOS_GRUPO]],
        }
        for grupo, indices in grupos
    ]

    return {
        "umbral": umbral,
        "n_grupos": len(miembros),
        "n_casi_duplicados": sum(len(indices) - 1 for _, indices in grupos),
        "n_grupos_con_duplicados": len(grupos),
        "grupos": detalles,
    }


def informe_calidad(registros: list[dict[str, Any]]) -> dict[str, Any]:
    """Auditoría completa del dataset etiquetado (todo calculado sobre datos reales).

    `registros` es una lista de diccionarios con las claves `texto`, `categoria`
    y `prioridad` (más `solicitud_id`, opcional).
    """
    total = len(registros)
    if total == 0:
        return {"total": 0}

    textos = [r["texto"] for r in registros]

    # --- Conteos y desbalance -------------------------------------------------
    por_categoria = Counter(r["categoria"] for r in registros)
    por_prioridad = Counter(r["prioridad"] for r in registros)

    conteos_cat = list(por_categoria.values())
    maximo, minimo = max(conteos_cat), min(conteos_cat)
    media = float(np.mean(conteos_cat))
    desbalance = {
        "maximo_por_clase": int(maximo),
        "minimo_por_clase": int(minimo),
        "razon_max_min": round(maximo / minimo, 3) if minimo else None,
        "coeficiente_variacion": round(float(np.std(conteos_cat) / media), 4) if media else 0.0,
    }

    # --- Longitud de los textos (en palabras) ---------------------------------
    longitudes = [len(texto.split()) for texto in textos]
    longitud = {
        "min_palabras": int(min(longitudes)),
        "max_palabras": int(max(longitudes)),
        "media_palabras": round(float(np.mean(longitudes)), 2),
        "mediana_palabras": float(np.median(longitudes)),
    }

    # --- Duplicados exactos (por texto normalizado) ---------------------------
    normalizados = [normalizar(texto) for texto in textos]
    conteo_normalizado = Counter(normalizados)
    duplicados_exactos = [t for t, n in conteo_normalizado.items() if n > 1]
    n_exactos_extra = sum(n - 1 for n in conteo_normalizado.values() if n > 1)

    # --- Casi-duplicados ------------------------------------------------------
    casi = detectar_casi_duplicados(textos)

    # --- Etiquetas contradictorias: mismo texto (normalizado) con etiqueta distinta
    etiquetas_por_texto: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for registro, normalizado in zip(registros, normalizados):
        etiquetas_por_texto[normalizado].add(
            (registro["categoria"], registro["prioridad"])
        )
    contradictorias = [
        {
            "texto": texto,
            "etiquetas": [{"categoria": c, "prioridad": p} for c, p in sorted(etiquetas)],
        }
        for texto, etiquetas in etiquetas_por_texto.items()
        if len({c for c, _ in etiquetas}) > 1
    ]

    # --- Vocabulario único ----------------------------------------------------
    vocabulario: set[str] = set()
    for texto in textos:
        vocabulario.update(tokenizar(texto))

    return {
        "total": total,
        "por_categoria": dict(sorted(por_categoria.items(), key=lambda par: -par[1])),
        "por_prioridad": dict(sorted(por_prioridad.items(), key=lambda par: -par[1])),
        "desbalance": desbalance,
        "longitud": longitud,
        "duplicados_exactos": {
            "grupos": len(duplicados_exactos),
            "registros_extra": n_exactos_extra,
            "ejemplos": [t[:160] for t in duplicados_exactos[:5]],
        },
        "casi_duplicados": {
            "umbral": casi["umbral"],
            "n_grupos": casi["n_grupos"],
            "registros_extra": casi["n_casi_duplicados"],
            "n_grupos_con_duplicados": casi["n_grupos_con_duplicados"],
            "grupos": casi["grupos"][:10],
        },
        "etiquetas_contradictorias": {
            "n": len(contradictorias),
            "ejemplos": contradictorias[:5],
        },
        "vocabulario_unico": len(vocabulario),
    }
