"""Servicio de informe del agente (Fase A4).

Genera, desde la base de datos y el modelo activo real, un informe en dos
formatos equivalentes:
  * Markdown: legible para la defensa y la docente.
  * JSON: estructurado, para que la interfaz (Fase B) vuelva a renderizar
    tablas y matrices como mapas de calor.

Secciones (a–i):
  a) cabecera: fecha, versión activa, conjunto de prueba, tamaños y hash corto;
  b) calidad del dataset (balance, duplicados, casi-duplicados, contradicciones,
     longitudes y vocabulario);
  c) parámetros del modelo y comparación de los 3 algoritmos;
  d) métricas de categoría y prioridad en prueba fija y EXTERNA con IC de Wilson;
  e) matrices de confusión (categoría 8×8 y prioridad 3×3) absolutas y normalizadas;
  f) baselines, calibración (Brier, ECE y tabla), curva cobertura-precisión,
     análisis de errores y curva de aprendizaje;
  g) eficiencia medida (Fase A3) y evolución por versión válida;
  h) ejemplo de proceso con 2 solicitudes (11 etapas de la traza + matriz
     documento-término TF-IDF reducida y puntajes por clase);
  i) pie con las librerías y versiones realmente instaladas.

Ningún valor se inventa: todo proviene de la base de datos, del binario del
modelo activo o de `importlib.metadata`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from datetime import datetime
from importlib import metadata
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorias import CATEGORIAS_SEED
from app.config import settings
from app.models import ConjuntoPruebaFijo, Informe, Modelo
from app.servicio_modelo import (
    CLASES_PRIORIDAD,
    deserializar,
    etiquetas_entrenamiento,
    etiquetas_prueba_externa,
    modelo_activo,
    parametros_modelo_activo,
    version_conjunto_prueba,
)
from ml import calidad, inferencia
from ml.preprocesamiento import texto_limpio

# Distribuciones cuyas versiones se reportan en el pie del informe.
_DISTRIBUCIONES: tuple[str, ...] = (
    "scikit-learn",
    "numpy",
    "scipy",
    "pandas",
    "joblib",
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "psycopg2-binary",
    "python-dotenv",
    "pytest",
    "httpx",
)


# ---------------------------------------------------------------------------
# Utilidades numéricas y de formato
# ---------------------------------------------------------------------------


def _wilson(aciertos: int, total: int, z: float = 1.96) -> dict[str, Any] | None:
    """Intervalo de confianza de Wilson para una proporción (Ecuación 17).

    Devuelve el valor puntual y los límites inferior/superior al 95 % (z = 1.96).
    Se usa porque es fiable incluso con pocos casos o proporciones extremas.
    """
    if total <= 0:
        return None
    p = aciertos / total
    denom = 1 + z * z / total
    centro = (p + z * z / (2 * total)) / denom
    margen = (z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / denom
    return {
        "valor": round(p, 4),
        "bajo": round(max(0.0, centro - margen), 4),
        "alto": round(min(1.0, centro + margen), 4),
        "n": total,
        "aciertos": int(aciertos),
        "z": z,
    }


def _aciertos(matriz: list[list[int]]) -> int:
    """Nº de aciertos = suma de la diagonal de la matriz de confusión."""
    return sum(int(matriz[i][i]) for i in range(len(matriz)) if i < len(matriz[i]))


def _matriz_normalizada(matriz: list[list[int]]) -> list[list[float]]:
    """Normaliza la matriz por fila (cada fila suma 1; fila vacía queda en 0)."""
    salida: list[list[float]] = []
    for fila in matriz:
        total = sum(int(v) for v in fila)
        salida.append([round(int(v) / total, 4) if total else 0.0 for v in fila])
    return salida


def _wilson_por_clase(
    etiquetas: list[str], matriz: list[list[int]]
) -> list[dict[str, Any]]:
    """IC de Wilson de la precisión y el recall de cada clase (Ecuación 17).

    TP = diagonal, FP = suma de la columna (sin la diagonal), FN = suma de la fila
    (sin la diagonal). Precisión = TP/(TP+FP); recall = TP/(TP+FN).
    """
    salida: list[dict[str, Any]] = []
    n = len(etiquetas)
    for i, clase in enumerate(etiquetas):
        tp = int(matriz[i][i]) if i < len(matriz) and i < len(matriz[i]) else 0
        fp = sum(int(matriz[f][i]) for f in range(n) if f != i and i < len(matriz[f]))
        fn = sum(int(v) for j, v in enumerate(matriz[i]) if j != i) if i < len(matriz) else 0
        salida.append(
            {
                "clase": clase,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "soporte": tp + fn,
                "precision_wilson": _wilson(tp, tp + fp),
                "recall_wilson": _wilson(tp, tp + fn),
            }
        )
    return salida


def _pct(valor: Any, decimales: int = 1) -> str:
    """Formatea una proporción (0-1) como porcentaje."""
    if valor is None:
        return "—"
    return f"{float(valor) * 100:.{decimales}f}%"


def _pct100(valor: Any, decimales: int = 1) -> str:
    """Formatea un valor ya expresado en porcentaje (p. ej. 60 = 60 %)."""
    if valor is None:
        return "—"
    return f"{float(valor):.{decimales}f}%"


def _num(valor: Any, decimales: int = 4) -> str:
    """Formatea un número real (o guion si es nulo)."""
    if valor is None:
        return "—"
    return f"{float(valor):.{decimales}f}"


def _tabla(cabeceras: list[str], filas: list[list[Any]]) -> str:
    """Construye una tabla Markdown a partir de cabeceras y filas."""
    lineas = ["| " + " | ".join(cabeceras) + " |"]
    lineas.append("| " + " | ".join("---" for _ in cabeceras) + " |")
    for fila in filas:
        lineas.append("| " + " | ".join(str(celda) for celda in fila) + " |")
    return "\n".join(lineas)


def _rango_wilson(w: dict[str, Any] | None) -> str:
    """Representa un intervalo de Wilson como `valor [bajo, alto]`."""
    if not w:
        return "—"
    return f"{_pct(w['valor'])} [{_pct(w['bajo'])}, {_pct(w['alto'])}]"


def _librerias_instaladas() -> dict[str, str]:
    """Versiones realmente instaladas de las librerías principales."""
    salida: dict[str, str] = {}
    for nombre in _DISTRIBUCIONES:
        try:
            salida[nombre] = metadata.version(nombre)
        except metadata.PackageNotFoundError:  # pragma: no cover - depende del entorno
            continue
    return salida


def _hash_datos(
    registros: list[dict[str, Any]], externos: list[dict[str, Any]]
) -> str:
    """Hash corto (12 hex) que identifica la versión de los datos usados.

    Permite comprobar que dos informes se generaron con exactamente el mismo
    conjunto de textos y etiquetas.
    """
    lineas = [
        f"{r['solicitud_id']}|{texto_limpio(r['texto'])}|{r['categoria']}|{r['prioridad']}"
        for r in registros
    ]
    lineas += [
        f"ext|{texto_limpio(r['texto'])}|{r['categoria']}|{r['prioridad']}"
        for r in externos
    ]
    return hashlib.sha256("||".join(sorted(lineas)).encode("utf-8")).hexdigest()[:12]


def _default_json(obj: Any) -> Any:
    """Convertidor para tipos no serializables (numpy y fechas)."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Tipo no serializable: {type(obj)!r}")


def _a_json(valor: Any) -> Any:
    """Normaliza cualquier estructura a JSON puro (int/float/str/list/dict)."""
    return json.loads(json.dumps(valor, default=_default_json, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Ejemplos de proceso (sección h)
# ---------------------------------------------------------------------------


def _seleccionar_textos_prueba(
    artefacto: dict[str, Any], prueba_regs: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Selecciona 2 casos del conjunto de prueba: uno acertado y uno dudoso.

    * ALTA confianza: el caso acertado de mayor confianza.
    * DUDOSA: el caso con el MARGEN más bajo entre las dos clases top (será el que
      el agente derivaría a revisión humana).
    """
    modelo_cat = artefacto["modelo_categoria"]
    modelo_pri = artefacto["modelo_prioridad"]

    mejor_alta: tuple[float, str] | None = None
    peor_margen: tuple[float, str] | None = None

    for registro in prueba_regs:
        resultado = inferencia.predecir_solicitud(
            modelo_cat, modelo_pri, registro["texto"]
        )
        if resultado["categoria"] == registro["categoria"]:
            if mejor_alta is None or resultado["confianza"] > mejor_alta[0]:
                mejor_alta = (resultado["confianza"], registro["texto"])
        if peor_margen is None or resultado["margen"] < peor_margen[0]:
            peor_margen = (resultado["margen"], registro["texto"])

    seleccion: list[dict[str, str]] = []
    if mejor_alta is not None:
        seleccion.append({"texto": mejor_alta[1], "origen": "prueba_fija_alta_confianza"})
    if peor_margen is not None and (mejor_alta is None or peor_margen[1] != mejor_alta[1]):
        seleccion.append({"texto": peor_margen[1], "origen": "prueba_fija_dudosa"})
    return seleccion


def _ejemplo_proceso(
    artefacto: dict[str, Any], umbrales: dict[str, float], texto: str, origen: str
) -> dict[str, Any]:
    """Construye la traza completa de un texto + su matriz documento-término."""
    traza = inferencia.construir_traza(
        artefacto["modelo_categoria"],
        artefacto["modelo_prioridad"],
        texto,
        umbrales,
    )
    matriz_documento_termino = inferencia.terminos_tfidf(
        artefacto["modelo_categoria"], texto_limpio(texto), top_n=8
    )
    return {
        "texto": texto,
        "origen": origen,
        "traza": traza,
        "matriz_documento_termino": matriz_documento_termino,
    }


# ---------------------------------------------------------------------------
# Construcción del informe estructurado
# ---------------------------------------------------------------------------


def _bloque_metricas(
    prueba_fija: dict[str, Any],
    externa: dict[str, Any],
    etiquetas_fija: list[str],
    matriz_fija: list[list[int]],
    por_clase_fija: dict[str, Any],
    etiquetas_externa: list[str],
    matriz_externa: list[list[int]],
    por_clase_externa: dict[str, Any],
) -> dict[str, Any]:
    """Agrupa las métricas de una familia (categoría o prioridad) con IC de Wilson."""
    return {
        "prueba_fija": {
            **prueba_fija,
            "wilson_accuracy": _wilson(
                _aciertos(matriz_fija) if matriz_fija else 0,
                sum(sum(int(v) for v in f) for f in matriz_fija) if matriz_fija else 0,
            ),
            "wilson_por_clase": _wilson_por_clase(etiquetas_fija, matriz_fija)
            if matriz_fija
            else [],
            "metricas_por_clase": por_clase_fija,
        },
        "externa": {
            **externa,
            "wilson_accuracy": _wilson(
                _aciertos(matriz_externa)
                if matriz_externa
                else round(float(externa.get("accuracy") or 0) * int(externa.get("n") or 0)),
                sum(sum(int(v) for v in f) for f in matriz_externa)
                if matriz_externa
                else int(externa.get("n") or 0),
            ),
            "wilson_por_clase": _wilson_por_clase(etiquetas_externa, matriz_externa)
            if matriz_externa
            else [],
            "metricas_por_clase": por_clase_externa,
        },
    }


def _construir_datos(db: Session, opciones: dict[str, Any]) -> dict[str, Any]:
    """Reúne TODOS los datos del informe leyendo la base de datos y el modelo activo."""
    ahora = datetime.now()
    registros = etiquetas_entrenamiento(db)
    externos = etiquetas_prueba_externa(db)
    activo = modelo_activo(db)
    versiones = list(db.scalars(select(Modelo).order_by(Modelo.fecha)).all())
    version_prueba = version_conjunto_prueba(db)

    textos_usuario = [
        t.strip() for t in (opciones.get("textos_ejemplo") or []) if t and t.strip()
    ][:2]

    version = activo.version if activo else ""
    nombre_archivo = f"informe_agente_{version or 'sin-modelo'}_{ahora:%Y-%m-%d}"

    parametros = parametros_modelo_activo(db)
    umbrales = {
        "confianza": settings.umbral_confianza,
        "margen": settings.umbral_margen,
    }

    datos: dict[str, Any] = {
        "meta": {
            "generado_por": opciones.get("generado_por", ""),
            "opciones": {"textos_ejemplo": textos_usuario},
            "fecha_generacion": ahora.isoformat(timespec="seconds"),
        },
        "cabecera": {
            "fecha_generacion": ahora.isoformat(timespec="seconds"),
            "version_modelo": version or "sin-modelo",
            "version_prueba": version_prueba,
            "metodo_evaluacion": activo.metodo_evaluacion if activo else "",
            "n_entrenamiento": int((parametros or {}).get("n_entrenamiento") or 0),
            "n_prueba_fija": int((parametros or {}).get("n_prueba_fija") or 0),
            "n_prueba_externa": int((parametros or {}).get("n_prueba_externa") or 0),
            "n_pool_etiquetas": len(registros),
            "hash_datos": _hash_datos(registros, externos),
            "nombre_archivo": nombre_archivo,
            "umbrales": umbrales,
        },
        "calidad": calidad.informe_calidad(registros),
        "parametros": parametros or {},
        "librerias": _librerias_instaladas(),
    }

    if activo is None:
        # Sin modelo activo el informe queda reducido a la cabecera y la calidad.
        datos["comparacion_algoritmos"] = {}
        datos["metricas"] = {}
        datos["matrices_confusion"] = {}
        datos["baselines"] = {}
        datos["calibracion"] = {}
        datos["cobertura_precision"] = []
        datos["errores"] = []
        datos["curva_aprendizaje"] = {}
        datos["eficiencia"] = {}
        datos["evolucion"] = []
        datos["versiones_excluidas"] = [
            {"version": m.version, "motivo": m.motivo_invalidez or "no comparable"}
            for m in versiones
            if not m.valida_para_comparacion
        ]
        datos["ejemplos_proceso"] = []
        return _a_json(datos)

    evaluacion = activo.evaluacion or {}

    # --- Comparación de algoritmos (3 algoritmos, F1 de validación cruzada) ----
    hiper = (parametros or {}).get("comparacion_algoritmos", {})
    datos["comparacion_algoritmos"] = hiper

    # --- Métricas: categoría y prioridad, prueba fija y externa ---------------
    matriz_cat = activo.matriz_confusion or {}
    etiquetas_cat = matriz_cat.get("etiquetas", [])
    valores_cat = matriz_cat.get("matriz", [])
    matriz_pri = evaluacion.get("matriz_confusion_prioridad", {})
    etiquetas_pri = matriz_pri.get("etiquetas", [])
    valores_pri = matriz_pri.get("matriz", [])

    externa = evaluacion.get("prueba_externa", {}) or {}
    ext_matriz = (externa.get("matriz_confusion") or {}).get("matriz", [])
    ext_etiquetas = (externa.get("matriz_confusion") or {}).get("etiquetas", [])

    datos["metricas"] = {
        "categoria": _bloque_metricas(
            {
                "accuracy": activo.accuracy,
                "precision_macro": activo.precision_macro,
                "recall_macro": activo.recall_macro,
                "f1_macro": activo.f1_macro,
                "n": activo.n_prueba or activo.n_validacion,
            },
            {
                "accuracy": externa.get("accuracy"),
                "precision_macro": externa.get("precision_macro"),
                "recall_macro": externa.get("recall_macro"),
                "f1_macro": externa.get("f1_macro"),
                "n": externa.get("n", 0),
            },
            etiquetas_cat,
            valores_cat,
            activo.metricas_por_clase or {},
            ext_etiquetas,
            ext_matriz,
            externa.get("metricas_por_clase") or {},
        ),
        "prioridad": _bloque_metricas(
            {
                "accuracy": activo.accuracy_prioridad,
                "precision_macro": activo.precision_prioridad,
                "recall_macro": activo.recall_prioridad,
                "f1_macro": activo.f1_prioridad,
                "n": activo.n_prueba or activo.n_validacion,
            },
            {
                "accuracy": externa.get("accuracy_prioridad"),
                "f1_macro": externa.get("f1_prioridad"),
                "n": externa.get("n", 0),
            },
            etiquetas_pri,
            valores_pri,
            evaluacion.get("metricas_por_clase_prioridad", {}),
            ext_etiquetas,
            [],
            {},
        ),
    }

    # --- Matrices de confusión (absolutas y normalizadas por fila) -------------
    datos["matrices_confusion"] = {
        "categoria": {
            "etiquetas": etiquetas_cat,
            "absoluta": valores_cat,
            "normalizada": _matriz_normalizada(valores_cat) if valores_cat else [],
        },
        "prioridad": {
            "etiquetas": etiquetas_pri,
            "absoluta": valores_pri,
            "normalizada": _matriz_normalizada(valores_pri) if valores_pri else [],
        },
    }

    # --- Baselines, calibración, cobertura, errores y curva de aprendizaje -----
    datos["baselines"] = {
        "categoria": evaluacion.get("baselines_categoria", {}),
        "prioridad": evaluacion.get("baselines_prioridad", {}),
    }
    datos["calibracion"] = evaluacion.get("calibracion_categoria", {})
    datos["cobertura_precision"] = evaluacion.get("curva_cobertura_precision", [])
    datos["errores"] = evaluacion.get("errores_categoria", [])
    datos["curva_aprendizaje"] = activo.curva_aprendizaje or {}

    # --- Eficiencia (A3) y evolución por versión válida ------------------------
    datos["eficiencia"] = parametros.get("eficiencia") if parametros else activo.eficiencia
    datos["evolucion"] = [
        {
            "version": m.version,
            "activo": bool(m.activo),
            "algoritmo": m.algoritmo,
            "n_entrenamiento": len(m.ids_entrenamiento or []) or int(m.n_entrenamiento or 0),
            "n_prueba": m.n_prueba or m.n_validacion,
            "accuracy": m.accuracy,
            "f1_macro": m.f1_macro,
            "f1_prioridad": m.f1_prioridad,
            "version_prueba": m.version_prueba,
            "eficiencia": m.eficiencia or {},
        }
        for m in versiones
        if m.valida_para_comparacion
    ]
    datos["versiones_excluidas"] = [
        {
            "version": m.version,
            "n_entrenamiento": int(m.n_entrenamiento or 0),
            "motivo": m.motivo_invalidez or "no comparable",
        }
        for m in versiones
        if not m.valida_para_comparacion
    ]

    # --- Ejemplo de proceso (sección h) ---------------------------------------
    artefacto = deserializar(activo)
    umbrales_artefacto = artefacto.get("umbrales_revision") or umbrales
    ids_fijos = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())
    prueba_regs = [r for r in registros if r["solicitud_id"] in ids_fijos]

    if textos_usuario:
        seleccion = [{"texto": t, "origen": "usuario"} for t in textos_usuario]
    else:
        seleccion = _seleccionar_textos_prueba(artefacto, prueba_regs)

    datos["ejemplos_proceso"] = [
        _ejemplo_proceso(artefacto, umbrales_artefacto, item["texto"], item["origen"])
        for item in seleccion
    ]

    return _a_json(datos)


# ---------------------------------------------------------------------------
# Render Markdown
# ---------------------------------------------------------------------------


def _md_cabecera(datos: dict[str, Any]) -> list[str]:
    cab = datos["cabecera"]
    lineas = ["## 1. Cabecera\n"]
    lineas.append(f"- **Fecha de generación:** {cab['fecha_generacion']}")
    lineas.append(f"- **Versión del modelo activa:** {cab['version_modelo']}")
    lineas.append(f"- **Método de evaluación:** {cab['metodo_evaluacion'] or '—'}")
    lineas.append(f"- **Conjunto de prueba vigente:** {cab['version_prueba'] or 'sin reservar'}")
    lineas.append(f"- **Ejemplos de entrenamiento:** {cab['n_entrenamiento']}")
    lineas.append(f"- **Ejemplos de prueba fija:** {cab['n_prueba_fija']}")
    lineas.append(f"- **Ejemplos de prueba externa:** {cab['n_prueba_externa']}")
    lineas.append(f"- **Etiquetas del pool de entrenamiento:** {cab['n_pool_etiquetas']}")
    lineas.append(
        f"- **Hash corto de los datos (SHA-256, 12 hex):** `{cab['hash_datos']}`"
    )
    umbrales = cab["umbrales"]
    lineas.append(
        f"- **Umbrales de revisión (Ec. 9):** confianza ≥ {umbrales['confianza']:.0f}% "
        f"y margen ≥ {umbrales['margen']:.0f}%\n"
    )
    return lineas


def _md_calidad(datos: dict[str, Any]) -> list[str]:
    info = datos["calidad"]
    lineas = ["## 2. Calidad del dataset\n"]
    if not info.get("total"):
        lineas.append("> No hay etiquetas vigentes para analizar.\n")
        return lineas

    lineas.append(f"- **Etiquetas analizadas:** {info['total']}")
    lineas.append(f"- **Vocabulario único:** {info['vocabulario_unico']} términos\n")

    lineas.append("### 2.1 Distribución por categoría\n")
    lineas.append(
        _tabla(
            ["Categoría", "Nº ejemplos", "% del total"],
            [
                [clave, conteo, _pct(conteo / info["total"])]
                for clave, conteo in info["por_categoria"].items()
            ],
        )
    )
    desbalance = info["desbalance"]
    lineas.append(
        f"\n> Desbalance: razón máx/mín = **{_num(desbalance['razon_max_min'], 2)}**, "
        f"coeficiente de variación = **{_num(desbalance['coeficiente_variacion'], 3)}**.\n"
    )

    lineas.append("### 2.2 Distribución por prioridad\n")
    lineas.append(
        _tabla(
            ["Prioridad", "Nº ejemplos", "% del total"],
            [
                [clave, conteo, _pct(conteo / info["total"])]
                for clave, conteo in info["por_prioridad"].items()
            ],
        )
    )

    longitudes = info["longitud"]
    lineas.append("\n### 2.3 Longitud de los textos (palabras)\n")
    lineas.append(
        f"- Mínima: **{longitudes['min_palabras']}**, mediana: "
        f"**{longitudes['mediana_palabras']}**, media: "
        f"**{_num(longitudes['media_palabras'], 1)}**, máxima: "
        f"**{longitudes['max_palabras']}**.\n"
    )

    dup = info["duplicados_exactos"]
    casi = info["casi_duplicados"]
    contradictorias = info["etiquetas_contradictorias"]
    lineas.append("### 2.4 Duplicados, casi-duplicados y contradicciones\n")
    lineas.append(
        f"- Duplicados exactos: **{dup['grupos']}** grupos ({dup['registros_extra']} extra)."
    )
    lineas.append(
        f"- Casi-duplicados (coseno TF-IDF ≥ {casi['umbral']}): "
        f"**{casi['registros_extra']}** extra en **{casi['n_grupos_con_duplicados']}** grupos."
    )
    lineas.append(
        f"- Etiquetas contradictorias (mismo texto, categoría distinta): **{contradictorias['n']}**.\n"
    )
    return lineas


def _md_parametros(datos: dict[str, Any]) -> list[str]:
    params = datos["parametros"]
    lineas = ["## 3. Parámetros del modelo y comparación de algoritmos\n"]
    if not params:
        lineas.append("> No hay modelo activo: entrena el agente para ver sus parámetros.\n")
        return lineas

    tfidf = params["tfidf"]
    division = params["division"]
    hiper = params["hiperparametros"]
    lineas.append("### 3.1 Configuración del vectorizador TF-IDF\n")
    lineas.append(
        _tabla(
            ["Parámetro", "Valor"],
            [
                ["Nº de características TF-IDF", tfidf["n_caracteristicas"]],
                ["Tamaño del vocabulario", tfidf["tamano_vocabulario"]],
                ["ngram_range", f"[{tfidf['ngram_range'][0]}, {tfidf['ngram_range'][1]}]"],
                ["min_df", tfidf["min_df"]],
                ["sublinear_tf", tfidf["sublinear_tf"]],
                ["Nº de características (prioridad)", tfidf["n_caracteristicas_prioridad"]],
            ],
        )
    )

    lineas.append("\n### 3.2 Clasificadores e hiperparámetros por clase\n")
    cat = hiper["categoria"]
    pri = hiper["prioridad"]
    lineas.append(
        _tabla(
            ["Clase", "Algoritmo", "C", "alpha", "class_weight", "max_iter", "calibrado"],
            [
                [
                    "Categoría",
                    params["algoritmo_categoria"],
                    cat.get("C"),
                    cat.get("alpha"),
                    cat.get("class_weight"),
                    cat.get("max_iter"),
                    cat.get("calibrado"),
                ],
                [
                    "Prioridad",
                    params["algoritmo_prioridad"] or "—",
                    pri.get("C"),
                    pri.get("alpha"),
                    pri.get("class_weight"),
                    pri.get("max_iter"),
                    pri.get("calibrado"),
                ],
            ],
        )
    )

    lineas.append("\n### 3.3 División de datos y semilla\n")
    lineas.append(
        _tabla(
            ["Aspecto", "Valor"],
            [
                ["Esquema", division["esquema"]],
                ["Semilla", division["semilla"]],
                ["Entrenamiento", division["entrenamiento"]],
                ["Prueba fija", division["prueba_fija"]],
                ["Prueba externa", division["prueba_externa"]],
                ["Folds máximos", division["folds_max"]],
                ["Validación cruzada", division["validacion_cruzada"]],
            ],
        )
    )

    lineas.append("\n### 3.4 Comparación de los 3 algoritmos (F1 macro de validación cruzada)\n")
    comparacion = datos.get("comparacion_algoritmos") or {}
    for nombre, clave in (("Categoría", "categoria"), ("Prioridad", "prioridad")):
        detalle = comparacion.get(clave) or {}
        lineas.append(f"**{nombre}** — ganador: `{comparacion.get(f'ganador_{clave}', '—')}`\n")
        if not detalle:
            lineas.append("> Sin datos de comparación para esta versión.\n")
            continue
        filas = [
            [
                algoritmo,
                _pct(valores.get("f1_macro")),
                _pct(valores.get("accuracy")),
                _pct(valores.get("precision_macro")),
                _pct(valores.get("recall_macro")),
            ]
            for algoritmo, valores in detalle.items()
        ]
        lineas.append(
            _tabla(
                ["Algoritmo", "F1 macro", "Accuracy", "Precisión macro", "Recall macro"],
                filas,
            )
        )
        lineas.append("")

    lineas.append(
        "> Leyenda de ecuaciones: TF-IDF en la vectorización (Ec. 1–3), puntaje lineal "
        "por clase (Ec. 4), objetivo de la SVM (Ec. 5), Naive Bayes como algoritmo "
        "comparado (Ec. 19) y softmax de la regresión logística (Ec. 20).\n"
    )
    return lineas


def _md_metricas(datos: dict[str, Any]) -> list[str]:
    lineas = ["## 4. Métricas de categoría y prioridad (con IC de Wilson)\n"]
    metricas = datos.get("metricas") or {}
    if not metricas:
        lineas.append("> No hay modelo activo: entrena el agente para ver las métricas.\n")
        return lineas

    for familia, titulo in (("categoria", "Categoría"), ("prioridad", "Prioridad")):
        bloque = metricas[familia]
        lineas.append(f"### 4.{1 if familia == 'categoria' else 2} {titulo}\n")
        lineas.append(
            _tabla(
                ["Conjunto", "N", "Accuracy (IC 95 %)", "Precisión macro", "Recall macro", "F1 macro"],
                [
                    [
                        "Prueba fija",
                        bloque["prueba_fija"].get("n", 0),
                        _rango_wilson(bloque["prueba_fija"].get("wilson_accuracy")),
                        _pct(bloque["prueba_fija"].get("precision_macro")),
                        _pct(bloque["prueba_fija"].get("recall_macro")),
                        _pct(bloque["prueba_fija"].get("f1_macro")),
                    ],
                    [
                        "Prueba externa",
                        bloque["externa"].get("n", 0),
                        _rango_wilson(bloque["externa"].get("wilson_accuracy")),
                        _pct(bloque["externa"].get("precision_macro")),
                        _pct(bloque["externa"].get("recall_macro")),
                        _pct(bloque["externa"].get("f1_macro")),
                    ],
                ],
            )
        )
        lineas.append("")

        por_clase = bloque["prueba_fija"].get("metricas_por_clase") or {}
        if por_clase:
            lineas.append(f"#### {titulo} — métricas por clase (Ec. 10–12)\n")
            lineas.append(
                _tabla(
                    ["Clase", "Precisión", "Recall", "F1", "Soporte"],
                    [
                        [
                            clase,
                            _pct(m.get("precision")),
                            _pct(m.get("recall")),
                            _pct(m.get("f1")),
                            m.get("soporte", 0),
                        ]
                        for clase, m in por_clase.items()
                    ],
                )
            )
            lineas.append("")

        if bloque["prueba_fija"].get("wilson_por_clase"):
            lineas.append(f"#### {titulo} — IC de Wilson por clase (Ec. 17)\n")
            lineas.append(
                _tabla(
                    ["Clase", "Precisión IC 95 %", "Recall IC 95 %", "Soporte"],
                    [
                        [
                            fila["clase"],
                            _rango_wilson(fila["precision_wilson"]),
                            _rango_wilson(fila["recall_wilson"]),
                            fila["soporte"],
                        ]
                        for fila in bloque["prueba_fija"]["wilson_por_clase"]
                    ],
                )
            )
            lineas.append("")
    return lineas


def _md_matrices(datos: dict[str, Any]) -> list[str]:
    lineas = ["## 5. Matrices de confusión (absolutas y normalizadas por fila)\n"]
    matrices = datos.get("matrices_confusion") or {}
    if not matrices:
        lineas.append("> No hay modelo activo: entrena el agente para ver las matrices.\n")
        return lineas

    for clave, titulo in (("categoria", "Categoría (8×8)"), ("prioridad", "Prioridad (3×3)")):
        bloque = matrices.get(clave) or {}
        etiquetas = bloque.get("etiquetas") or []
        absoluta = bloque.get("absoluta") or []
        normalizada = bloque.get("normalizada") or []
        lineas.append(f"### 5.{1 if clave == 'categoria' else 2} {titulo}\n")
        if not etiquetas or not absoluta:
            lineas.append("> Sin matriz disponible.\n")
            continue
        cabeceras = ["real \\ pred", *[e[:8] for e in etiquetas]]
        lineas.append("**Absoluta (nº de casos)**\n")
        lineas.append(
            _tabla(
                cabeceras,
                [[etiquetas[i], *[str(v) for v in fila]] for i, fila in enumerate(absoluta)],
            )
        )
        lineas.append("\n**Normalizada por fila (proporción)**\n")
        lineas.append(
            _tabla(
                cabeceras,
                [[etiquetas[i], *[_pct(v) for v in fila]] for i, fila in enumerate(normalizada)],
            )
        )
        lineas.append("")
    return lineas


def _md_evaluacion_ampliada(datos: dict[str, Any]) -> list[str]:
    lineas = ["## 6. Baselines, calibración y curvas\n"]

    # Baselines
    lineas.append("### 6.1 Comparación con baselines\n")
    baselines = datos.get("baselines") or {}
    metricas = datos.get("metricas") or {}
    if not baselines:
        lineas.append("> Sin datos de baselines.\n")
    else:
        for clave, titulo in (("categoria", "Categoría"), ("prioridad", "Prioridad")):
            base = baselines.get(clave) or {}
            mayoritaria = base.get("mayoritaria", {})
            aleatoria = base.get("aleatoria_estratificada", {})
            fija = (metricas.get(clave, {}) or {}).get("prueba_fija", {})
            filas = [
                [
                    "Agente (modelo activo)",
                    _pct(fija.get("accuracy")),
                    _pct(fija.get("f1_macro")),
                ],
                [
                    f"Clase mayoritaria ({mayoritaria.get('clase', '—')})",
                    _pct(mayoritaria.get("accuracy")),
                    _pct(mayoritaria.get("f1_macro")),
                ],
                [
                    "Aleatoria estratificada",
                    _pct(aleatoria.get("accuracy")),
                    _pct(aleatoria.get("f1_macro")),
                ],
            ]
            lineas.append(f"**{titulo}**\n")
            lineas.append(_tabla(["Clasificador", "Accuracy", "F1 macro"], filas))
            lineas.append("")

    # Calibración
    lineas.append("### 6.2 Calibración de la confianza (Ec. 6, 15, 16)\n")
    calibracion = datos.get("calibracion") or {}
    tabla = calibracion.get("tabla") or []
    if tabla:
        lineas.append(
            _tabla(
                ["Rango de confianza", "N", "Confianza media", "Exactitud real"],
                [
                    [
                        f"[{_pct(fila['rango'][0])}, {_pct(fila['rango'][1])})",
                        fila["n"],
                        _pct(fila["confianza_media"]),
                        _pct(fila["exactitud"]),
                    ]
                    for fila in tabla
                ],
            )
        )
        lineas.append(
            f"\n> Brier score: **{_num(calibracion.get('brier'), 4)}** · "
            f"ECE: **{_num(calibracion.get('ece'), 4)}** · casos: **{calibracion.get('n', 0)}**.\n"
        )
    else:
        lineas.append("> Sin datos de calibración.\n")

    # Cobertura-precisión
    lineas.append("### 6.3 Curva cobertura-precisión y umbral de revisión (Ec. 9)\n")
    cobertura = datos.get("cobertura_precision") or []
    if cobertura:
        lineas.append(
            _tabla(
                ["Umbral de confianza", "Cobertura", "N aceptados", "Precisión"],
                [
                    [
                        _pct(punto["umbral"], 0),
                        _pct(punto["cobertura"]),
                        punto["n"],
                        _pct(punto["precision"]),
                    ]
                    for punto in cobertura
                ],
            )
        )
        lineas.append("")
    else:
        lineas.append("> Sin curva de cobertura-precisión.\n")

    # Errores
    lineas.append("### 6.4 Análisis de errores\n")
    errores = datos.get("errores") or []
    if errores:
        lineas.append(
            _tabla(
                ["Texto (recortado)", "Real", "Predicha", "Confianza"],
                [
                    [f"`{error['texto'][:60]}`", error["real"], error["predicha"], _pct(error["confianza"])]
                    for error in errores[:15]
                ],
            )
        )
        lineas.append("")
    else:
        lineas.append("> El modelo activo no cometió errores en el conjunto de prueba.\n")

    # Curva de aprendizaje
    lineas.append("### 6.5 Curva de aprendizaje\n")
    curva = datos.get("curva_aprendizaje") or {}
    if curva.get("tamanos"):
        lineas.append(
            _tabla(
                ["Nº ejemplos", "F1 entrenamiento", "F1 validación"],
                [
                    [tamano, _pct(f1_train), _pct(f1_val)]
                    for tamano, f1_train, f1_val in zip(
                        curva["tamanos"], curva["f1_entrenamiento"], curva["f1_validacion"]
                    )
                ],
            )
        )
        lineas.append("")
    else:
        lineas.append("> Sin curva de aprendizaje disponible.\n")
    return lineas


def _md_eficiencia_evolucion(datos: dict[str, Any]) -> list[str]:
    lineas = ["## 7. Eficiencia medida y evolución por versión\n"]
    eficiencia = datos.get("eficiencia") or {}
    lineas.append("### 7.1 Eficiencia del modelo activo\n")
    if eficiencia:
        lineas.append(
            _tabla(
                ["Métrica", "Valor"],
                [
                    ["Tiempo de entrenamiento", f"{_num(eficiencia.get('tiempo_entrenamiento_s'), 3)} s"],
                    ["Tamaño del modelo serializado", f"{_num(eficiencia.get('tamano_modelo_kb'), 2)} KB"],
                    ["Nº de predicciones medidas", eficiencia.get("n_predicciones", 0)],
                    ["Textos distintos usados", eficiencia.get("n_textos_distintos", 0)],
                    ["Latencia media", f"{_num(eficiencia.get('latencia_media_ms'), 3)} ms"],
                    ["Latencia p95", f"{_num(eficiencia.get('latencia_p95_ms'), 3)} ms"],
                ],
            )
        )
        lineas.append("")
    else:
        lineas.append("> Sin medición de eficiencia registrada para esta versión.\n")

    lineas.append("### 7.2 Evolución por versión válida (sin fuga de datos)\n")
    evolucion = datos.get("evolucion") or []
    if not evolucion:
        lineas.append("> No hay versiones comparables válidas todavía.\n")
    else:
        lineas.append(
            _tabla(
                [
                    "Versión",
                    "Algoritmo",
                    "Entren. (s)",
                    "Modelo (KB)",
                    "Latencia p95 (ms)",
                    "Prueba",
                    "Accuracy cat.",
                    "F1 cat.",
                    "F1 prioridad",
                ],
                [
                    [
                        fila["version"] + (" (activa)" if fila["activo"] else ""),
                        fila["algoritmo"],
                        _num((fila.get("eficiencia") or {}).get("tiempo_entrenamiento_s"), 3),
                        _num((fila.get("eficiencia") or {}).get("tamano_modelo_kb"), 2),
                        _num((fila.get("eficiencia") or {}).get("latencia_p95_ms"), 3),
                        fila["n_prueba"],
                        _pct(fila["accuracy"]),
                        _pct(fila["f1_macro"]),
                        _pct(fila["f1_prioridad"]),
                    ]
                    for fila in evolucion
                ],
            )
        )
        lineas.append("")

    excluidas = datos.get("versiones_excluidas") or []
    if excluidas:
        lineas.append("### 7.3 Versiones excluidas de la comparación (fuga de datos)\n")
        lineas.append(
            _tabla(
                ["Versión", "Ejemplos (histórico)", "Motivo de exclusión"],
                [[f["version"], f["n_entrenamiento"], f["motivo"]] for f in excluidas],
            )
        )
        lineas.append("")
    return lineas


def _md_ejemplo_proceso(datos: dict[str, Any]) -> list[str]:
    lineas = ["## 8. Ejemplo de proceso del agente (las 11 etapas)\n"]
    ejemplos = datos.get("ejemplos_proceso") or []
    if not ejemplos:
        lineas.append("> No hay conjunto de prueba ni textos de ejemplo disponibles.\n")
        return lineas

    lineas.append(
        "Diagrama del pipeline: **texto → normalización → tokens/stopwords → "
        "n-gramas → TF-IDF → clasificador → calibración → decisión por umbral/margen "
        "→ resultado o revisión humana**.\n"
    )

    for indice, ejemplo in enumerate(ejemplos, start=1):
        traza = ejemplo["traza"]
        decision = traza["decision"]
        lineas.append(f"### 8.{indice} Ejemplo {indice} — origen: `{ejemplo['origen']}`\n")
        lineas.append(f"- **1. Texto original:** `{traza['texto_original']}`")
        lineas.append(f"- **2. Texto normalizado:** `{traza['texto_normalizado']}`")
        lineas.append(
            f"- **3. Tokens ({len(traza['tokens'])}):** "
            + ", ".join(f"`{t}`" for t in traza["tokens"])
        )
        lineas.append(
            f"- **4. Tokens sin stopwords ({len(traza['tokens_sin_stopwords'])}):** "
            + (", ".join(f"`{t}`" for t in traza["tokens_sin_stopwords"]) or "—")
        )
        eliminadas = traza.get("stopwords_eliminadas") or []
        lineas.append(
            "- **Stopwords eliminadas:** "
            + (", ".join(f"`{t}`" for t in eliminadas) or "—")
        )
        lineas.append(
            f"- **5. N-gramas generados ({len(traza['n_gramas'])}):** "
            + (", ".join(f"`{g}`" for g in traza["n_gramas"]) or "—")
        )

        lineas.append("\n**6. Términos con mayor peso TF-IDF (Ec. 1–3)**\n")
        lineas.append(
            _tabla(
                ["Término", "tf", "idf", "tf-idf"],
                [
                    [f"`{t['termino']}`", t["tf"], _num(t["idf"], 4), _num(t["tfidf"], 5)]
                    for t in traza["terminos_tfidf"]
                ],
            )
        )

        lineas.append("\n**Matriz documento-término TF-IDF reducida (8 términos más relevantes)**\n")
        lineas.append(
            _tabla(
                ["Documento \\ término", *[f"`{t['termino']}`" for t in ejemplo["matriz_documento_termino"]]],
                [
                    [
                        "peso tf-idf",
                        *[_num(t["tfidf"], 5) for t in ejemplo["matriz_documento_termino"]],
                    ]
                ],
            )
        )

        lineas.append("\n**7. Puntajes de decisión por clase (Ec. 4)**\n")
        lineas.append(
            _tabla(
                ["Clase", "s_c(x)"],
                [[f"`{p['clase']}`", _num(p["puntaje"], 5)] for p in traza["puntajes_categoria"]],
            )
        )

        lineas.append("\n**8. Probabilidades calibradas de categoría (Ec. 6, 7)**\n")
        lineas.append(
            _tabla(
                ["Clase", "Probabilidad"],
                [
                    [f"`{p['clase']}`", _pct(p["probabilidad"])]
                    for p in traza["probabilidades_categoria"]
                ],
            )
        )

        lineas.append("\n**9–10. Margen y decisión (Ec. 8, 9)**\n")
        lineas.append(
            _tabla(
                ["Concepto", "Valor"],
                [
                    ["Confianza (categoría)", _pct100(decision["confianza"], 2)],
                    ["Umbral de confianza", _pct100(decision["umbral_confianza"], 0)],
                    ["¿Cumple confianza?", decision["cumple_confianza"]],
                    ["Margen p₁ − p₂", _pct100(decision["margen"], 2)],
                    ["Umbral de margen", _pct100(decision["umbral_margen"], 0)],
                    ["¿Cumple margen?", decision["cumple_margen"]],
                    ["Categoría final", f"`{decision['categoria']}`"],
                    ["Prioridad final", f"`{decision['prioridad']}`"],
                    ["**Decisión final**", "**automática**" if decision["resultado"] == "automatica" else "**revisión humana**"],
                ],
            )
        )

        lineas.append("\n**11. Resumen equivalente para la PRIORIDAD**\n")
        lineas.append(
            _tabla(
                ["Clase", "Puntaje s_c(x)", "Probabilidad"],
                [
                    [
                        f"`{p['clase']}`",
                        _num(p["puntaje"], 5),
                        _pct(
                            next(
                                (
                                    q["probabilidad"]
                                    for q in traza["prioridad"]["probabilidades"]
                                    if q["clase"] == p["clase"]
                                ),
                                0.0,
                            )
                        ),
                    ]
                    for p in traza["prioridad"]["puntajes"]
                ],
            )
        )
        lineas.append(
            f"\n> Prioridad con mayor probabilidad: **`{traza['prioridad']['clase']}`** "
            f"(confianza {_pct100(traza['prioridad']['confianza'], 2)}, "
            f"margen {_pct100(traza['prioridad']['margen'], 2)}).\n"
        )
    return lineas


def _md_librerias(datos: dict[str, Any]) -> list[str]:
    librerias = datos.get("librerias") or {}
    lineas = ["## 9. Librerías y versiones instaladas\n"]
    lineas.append(
        "> Versiones leídas realmente del entorno con `importlib.metadata` "
        "(ninguna escrita a mano).\n"
    )
    lineas.append(
        _tabla(["Librería", "Versión instalada"], [[nombre, version] for nombre, version in librerias.items()])
    )
    lineas.append(
        "\n> El agente usa `scikit-learn` (TfidfVectorizer, MultinomialNB, "
        "LogisticRegression, LinearSVC, CalibratedClassifierCV, DummyClassifier, "
        "StratifiedKFold, StratifiedGroupKFold, learning_curve, metrics) sobre "
        "`FastAPI` + `SQLAlchemy` + `PostgreSQL` (Supabase).\n"
    )
    return lineas


def _render_markdown(datos: dict[str, Any]) -> str:
    """Compone el informe Markdown completo a partir del JSON estructurado."""
    partes: list[str] = [
        "# Informe del agente · Kiosco Ciudadano (Equipo # 3)\n",
        "Documento generado automáticamente desde la base de datos y el modelo "
        "activo. Todas las cifras son reales y reproducibles (no hay valores "
        "simulados).\n",
    ]
    partes += _md_cabecera(datos)
    partes += _md_calidad(datos)
    partes += _md_parametros(datos)
    partes += _md_metricas(datos)
    partes += _md_matrices(datos)
    partes += _md_evaluacion_ampliada(datos)
    partes += _md_eficiencia_evolucion(datos)
    partes += _md_ejemplo_proceso(datos)
    partes += _md_librerias(datos)
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# API pública del servicio
# ---------------------------------------------------------------------------


def generar_informe(db: Session, opciones: dict[str, Any] | None = None) -> dict[str, Any]:
    """Genera el informe del agente (Markdown + JSON) sin persistirlo.

    `opciones` admite: `textos_ejemplo` (hasta 2 textos) y `generado_por`.
    Devuelve un diccionario con `markdown`, `json`, `version_modelo` y
    `nombre_base` (para nombrar los archivos descargables).
    """
    opciones = opciones or {}
    datos = _construir_datos(db, opciones)
    markdown = _render_markdown(datos)
    return {
        "markdown": markdown,
        "json": datos,
        "version_modelo": datos["cabecera"]["version_modelo"],
        "nombre_base": datos["cabecera"]["nombre_archivo"],
    }


def generar_y_guardar(db: Session, opciones: dict[str, Any] | None = None) -> Informe:
    """Genera el informe y lo persiste en la tabla `informes`.

    Registra el estado (`en_proceso` → `completado`/`error`) para que la interfaz
    pueda consultarlo. Si algo falla, se guarda el motivo y NO se propaga la
    excepción (el informe queda marcado con estado `error`).
    """
    opciones = opciones or {}
    limpio = {
        "textos_ejemplo": [t for t in (opciones.get("textos_ejemplo") or []) if t],
        "generado_por": opciones.get("generado_por", ""),
    }
    informe = Informe(
        version_modelo="",
        generado_por=limpio["generado_por"],
        estado="en_proceso",
        opciones=limpio,
    )
    db.add(informe)
    db.commit()
    db.refresh(informe)

    try:
        resultado = generar_informe(db, limpio)
        informe.contenido_md = resultado["markdown"]
        informe.contenido_json = resultado["json"]
        informe.version_modelo = resultado["version_modelo"]
        informe.estado = "completado"
        informe.error = ""
    except Exception as error:  # pragma: no cover - depende de los datos
        informe.estado = "error"
        informe.error = str(error)[:300]

    db.commit()
    db.refresh(informe)
    return informe


def nombre_archivo(informe: Informe, formato: str) -> str:
    """Nombre de archivo descargable `informe_agente_{version}_{AAAA-MM-DD}.{ext}`."""
    base = (informe.contenido_json or {}).get("cabecera", {}).get("nombre_archivo")
    if not base:
        fecha = informe.fecha.strftime("%Y-%m-%d") if informe.fecha else datetime.now().strftime("%Y-%m-%d")
        base = f"informe_agente_{informe.version_modelo or 'sin-modelo'}_{fecha}"
    return f"{base}.{formato}"


def _matriz_a_csv(etiquetas: list[str], matriz: list[list[Any]]) -> str:
    """Serializa una matriz de confusión a CSV (primera fila y columna = etiquetas)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["real\\pred", *etiquetas])
    for indice, fila in enumerate(matriz):
        etiqueta = etiquetas[indice] if indice < len(etiquetas) else str(indice)
        escritor.writerow([etiqueta, *fila])
    return buffer.getvalue()


def construir_zip(informe: Informe) -> bytes:
    """Construye el ZIP descargable con el .md, el .json y los CSV de matrices."""
    datos = informe.contenido_json or {}
    base = (datos.get("cabecera") or {}).get("nombre_archivo") or nombre_archivo(informe, "md").rsplit(".", 1)[0]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr(f"{base}.md", informe.contenido_md or "")
        archivo.writestr(f"{base}.json", json.dumps(datos, ensure_ascii=False, indent=2))
        matrices = datos.get("matrices_confusion") or {}
        for clave, nombre in (
            ("categoria", "matriz_confusion_categoria"),
            ("prioridad", "matriz_confusion_prioridad"),
        ):
            bloque = matrices.get(clave) or {}
            etiquetas = bloque.get("etiquetas") or []
            for sufijo, matriz in (
                ("", bloque.get("absoluta")),
                ("_normalizada", bloque.get("normalizada")),
            ):
                if not etiquetas or not matriz:
                    continue
                archivo.writestr(
                    f"{nombre}{sufijo}.csv", _matriz_a_csv(etiquetas, matriz)
                )
    return buffer.getvalue()


def render_ejemplos_proceso(contenido_json: dict[str, Any]) -> str:
    """Renderiza SOLO la sección de ejemplo de proceso (usada por la CLI)."""
    datos = dict(contenido_json or {})
    cabecera = datos.get("cabecera") or {}
    encabezado = (
        "# Ejemplo de proceso del agente\n\n"
        f"- **Versión del modelo:** {cabecera.get('version_modelo', 'sin-modelo')}\n"
        f"- **Hash de los datos:** `{cabecera.get('hash_datos', '')}`\n"
        f"- **Fecha:** {cabecera.get('fecha_generacion', '')}\n\n"
    )
    return encabezado + "\n".join(_md_ejemplo_proceso(datos))
