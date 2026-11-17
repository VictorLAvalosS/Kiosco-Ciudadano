"""Servicio de entrenamiento, versionado y activación del modelo.

Reglas de negocio clave:
  * Se entrena con TODAS las etiquetas vigentes, excluyendo siempre el conjunto
    de prueba fijo (para que las versiones sean comparables).
  * El conjunto de prueba fijo se reserva por GRUPOS de casi-duplicados: variantes
    de la misma frase nunca quedan a la vez en entrenamiento y prueba.
  * Una versión nueva solo se activa si su F1 macro mejora o iguala al de la
    versión activa MEDIDA SOBRE EL MISMO conjunto de prueba.
  * El binario serializado (joblib) se guarda en la propia base de datos, de modo
    que todo el equipo trabaja con el mismo modelo.
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, defer

from app.categorias import CATEGORIAS_SEED
from app.config import settings
from app.models import ConjuntoPruebaFijo, Etiqueta, Modelo, Solicitud
from ml import calidad, entrenamiento, inferencia
from ml.preprocesamiento import STOPWORDS, normalizar, tokenizar

# Caché en memoria de los modelos deserializados (por versión).
_CACHE: dict[str, dict[str, Any]] = {}

# Mínimo de ejemplos etiquetados para reservar un conjunto de prueba fijo.
MINIMO_PARA_FIJO = 40
# Proporción reservada para el conjunto de prueba fijo (1/5 = 20 %).
PROPORCION_PRUEBA = 0.2
# Nº de particiones del conjunto de prueba por grupos (20 % = 1/5).
PARTICIONES_PRUEBA = 5

CLASES_PRIORIDAD = ["ALTA", "MEDIA", "BAJA"]
_PALABRAS = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------


def etiquetas_vigentes(
    db: Session, excluir_origenes: set[str] | None = None
) -> list[dict[str, Any]]:
    """Devuelve todas las etiquetas vigentes junto al texto y origen de su solicitud.

    `excluir_origenes` permite dejar fuera, por ejemplo, el conjunto de prueba
    EXTERNO (`prueba_externa`), que nunca debe usarse para entrenar.
    """
    consulta = (
        select(
            Solicitud.id,
            Solicitud.texto,
            Etiqueta.prioridad,
            Etiqueta.categoria_id,
            Solicitud.origen,
        )
        .join(Etiqueta, Etiqueta.solicitud_id == Solicitud.id)
        .where(Etiqueta.vigente.is_(True))
    )
    if excluir_origenes:
        consulta = consulta.where(Solicitud.origen.notin_(excluir_origenes))
    filas = db.execute(consulta).all()

    from app.models import Categoria

    mapa = {c.id: c.clave for c in db.scalars(select(Categoria)).all()}
    return [
        {
            "solicitud_id": int(fila[0]),
            "texto": fila[1],
            "prioridad": fila[2],
            "categoria": mapa.get(fila[3], "otras"),
            "origen": fila[4],
        }
        for fila in filas
    ]


def etiquetas_entrenamiento(db: Session) -> list[dict[str, Any]]:
    """Etiquetas utilizables para entrenar y para reservar el conjunto de prueba.

    Excluye el conjunto de prueba EXTERNO, que por definición nunca se usa para
    entrenar (es una evaluación independiente).
    """
    return etiquetas_vigentes(db, excluir_origenes={"prueba_externa"})


def etiquetas_prueba_externa(db: Session) -> list[dict[str, Any]]:
    """Solicitudes etiquetadas que forman el conjunto de prueba EXTERNO."""
    return [
        registro
        for registro in etiquetas_vigentes(db)
        if registro.get("origen") == "prueba_externa"
    ]



def version_conjunto_prueba(db: Session) -> str:
    """Etiqueta de la versión actual del conjunto de prueba fijo (o cadena vacía)."""
    return db.scalar(select(func.max(ConjuntoPruebaFijo.version_prueba))) or ""


def regenerar_conjunto_prueba(db: Session, registros: list[dict[str, Any]]) -> tuple[set[int], str]:
    """Crea una nueva generación del conjunto de prueba fijo con split por grupos.

    - Agrupa los textos casi duplicados (similitud coseno TF-IDF >= 0.85).
    - Reserva el 20 % estratificado por categoría y por grupos (StratifiedGroupKFold).
    - Guarda la generación, la versión y el grupo de cada solicitud reservada.
    """
    if len(registros) < MINIMO_PARA_FIJO:
        return set(), ""

    textos = [r["texto"] for r in registros]
    claves = [r["categoria"] for r in registros]
    grupos = calidad.agrupar_casi_duplicados(textos)

    generacion = int(db.scalar(select(func.max(ConjuntoPruebaFijo.generacion))) or 0) + 1
    version = f"prueba-g{generacion}"

    indices_prueba: list[int] = []
    try:
        divisor = StratifiedGroupKFold(
            n_splits=PARTICIONES_PRUEBA, shuffle=True, random_state=42
        )
        _, prueba = next(divisor.split(textos, claves, groups=grupos))
        indices_prueba = [int(i) for i in prueba]
    except ValueError:
        # Respaldo si la estratificación por grupos no es viable.
        divisor = GroupShuffleSplit(n_splits=1, test_size=PROPORCION_PRUEBA, random_state=42)
        _, prueba = next(divisor.split(textos, claves, groups=grupos))
        indices_prueba = [int(i) for i in prueba]

    # Se reemplaza la generación anterior (el nuevo conjunto es el único vigente).
    db.execute(delete(ConjuntoPruebaFijo))
    for indice in indices_prueba:
        registro = registros[indice]
        db.add(
            ConjuntoPruebaFijo(
                solicitud_id=registro["solicitud_id"],
                generacion=generacion,
                version_prueba=version,
                grupo=grupos[indice],
            )
        )
    db.commit()
    return {registros[i]["solicitud_id"] for i in indices_prueba}, version


def _asegurar_conjunto_prueba(
    db: Session, registros: list[dict[str, Any]], regenerar: bool = False
) -> tuple[set[int], str]:
    """Devuelve (ids de prueba, versión del conjunto), regenerándolo si hace falta.

    Se regenera cuando no existe, cuando es una generación antigua (sin versión,
    creada antes del split por grupos) o cuando se pide explícitamente.
    """
    existentes = db.execute(
        select(ConjuntoPruebaFijo.solicitud_id, ConjuntoPruebaFijo.version_prueba)
    ).all()

    if existentes and not regenerar and all(fila[1] for fila in existentes):
        ids = {int(fila[0]) for fila in existentes}
        return ids, str(existentes[0][1])

    return regenerar_conjunto_prueba(db, registros)


# ---------------------------------------------------------------------------
# Serialización / caché
# ---------------------------------------------------------------------------


def _serializar(artefacto: dict[str, Any]) -> bytes:
    """Serializa el artefacto (pipelines + metadatos) con joblib."""
    buffer = io.BytesIO()
    joblib.dump(artefacto, buffer)
    return buffer.getvalue()


def deserializar(modelo: Modelo) -> dict[str, Any]:
    """Devuelve el artefacto del modelo, usando la caché en memoria."""
    if modelo.version in _CACHE:
        return _CACHE[modelo.version]
    artefacto = joblib.load(io.BytesIO(modelo.modelo_binario))
    _CACHE[modelo.version] = artefacto
    return artefacto


def modelo_activo(db: Session) -> Modelo | None:
    """Devuelve la fila de la versión activa (o None si no hay modelo)."""
    return db.scalars(
        select(Modelo)
        .options(defer(Modelo.modelo_binario))
        .where(Modelo.activo.is_(True))
    ).first()


# ---------------------------------------------------------------------------
# Control de fuga de datos: ¿es una versión comparable?
# ---------------------------------------------------------------------------


def version_valida_para_comparacion(
    modelo: Modelo, ids_prueba: set[int], tamano_pool: int
) -> tuple[bool, str]:
    """Indica si una versión puede compararse sobre el conjunto de prueba fijo.

    Regla: el entrenamiento NO debe compartir ningún id con el conjunto de prueba.

      * Con ids registrados → válida si la intersección es vacía.
      * Sin ids registrados (versiones anteriores a la migración 0003) → se marca
        inválida. Si además su nº de ejemplos supera el tamaño del pool disponible
        (dataset menos la prueba fija), con seguridad usó datos del conjunto de
        prueba y así se informa.
    """
    ids = set(int(x) for x in (modelo.ids_entrenamiento or []))
    if ids:
        if ids & ids_prueba:
            return False, "entrenada con datos del conjunto de prueba"
        return True, ""
    if int(modelo.n_entrenamiento or 0) > max(0, tamano_pool):
        return False, "entrenada con datos del conjunto de prueba"
    return False, "sin ids de entrenamiento registrados (versión anterior a la corrección)"


def evaluar_en_externo(
    artefacto: dict[str, Any], registros: list[dict[str, Any]]
) -> dict[str, Any]:
    """Evalúa el artefacto sobre el conjunto de prueba EXTERNO (nunca usado al entrenar)."""
    if not registros:
        return {}
    textos = [r["texto"] for r in registros]
    y_cat = [r["categoria"] for r in registros]
    y_pri = [r["prioridad"] for r in registros]
    metricas = entrenamiento.evaluar(
        artefacto["modelo_categoria"], textos, y_cat, [c["clave"] for c in CATEGORIAS_SEED]
    )
    metricas_pri = entrenamiento.evaluar(
        artefacto["modelo_prioridad"], textos, y_pri, CLASES_PRIORIDAD
    )
    return {
        "n": len(registros),
        "accuracy": float(metricas["accuracy"]),
        "precision_macro": float(metricas["precision_macro"]),
        "recall_macro": float(metricas["recall_macro"]),
        "f1_macro": float(metricas["f1_macro"]),
        "accuracy_prioridad": float(metricas_pri["accuracy"]),
        "f1_prioridad": float(metricas_pri["f1_macro"]),
        "metricas_por_clase": metricas["metricas_por_clase"],
        "matriz_confusion": {
            "etiquetas": metricas.get("etiquetas_matriz", []),
            "matriz": metricas.get("matriz_confusion", []),
        },
    }


# ---------------------------------------------------------------------------
# Entrenamiento
# ---------------------------------------------------------------------------


def medir_eficiencia(
    artefacto: dict[str, Any],
    tamano_binario_bytes: int,
    registros_prueba: list[dict[str, Any]],
    tiempo_entrenamiento_s: float,
    n_predicciones: int = 500,
    semilla: int = 42,
) -> dict[str, Any]:
    """Mide la eficiencia real del modelo (Fase A3).

    * tiempo de entrenamiento (s) — el de esta versión;
    * tamaño del binario serializado (KB);
    * latencia de predicción (media y percentil 95 en ms) medida sobre
      `n_predicciones` predicciones reales del conjunto de prueba. Si el conjunto
      tiene menos de 500 casos, se remuestrean con reposición (se documenta el
      número real de textos distintos).
    """
    textos = [r["texto"] for r in registros_prueba if r.get("texto")]
    base: dict[str, Any] = {
        "tiempo_entrenamiento_s": round(float(tiempo_entrenamiento_s), 4),
        "tamano_modelo_kb": round(tamano_binario_bytes / 1024, 2),
        "fecha_medicion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not textos:
        return {
            **base,
            "n_predicciones": 0,
            "n_textos_distintos": 0,
            "latencia_media_ms": None,
            "latencia_p95_ms": None,
        }

    rng = np.random.default_rng(semilla)
    indices = rng.integers(0, len(textos), size=n_predicciones)
    modelo_cat = artefacto["modelo_categoria"]
    modelo_pri = artefacto["modelo_prioridad"]

    latencias: list[float] = []
    for indice in indices:
        inicio = time.perf_counter()
        inferencia.predecir_solicitud(modelo_cat, modelo_pri, textos[int(indice)])
        latencias.append((time.perf_counter() - inicio) * 1000)

    arreglo = np.asarray(latencias, dtype=float)
    return {
        **base,
        "n_predicciones": int(arreglo.size),
        "n_textos_distintos": len(textos),
        "latencia_media_ms": round(float(arreglo.mean()), 3),
        "latencia_p95_ms": round(float(np.percentile(arreglo, 95)), 3),
    }


def _siguiente_version(db: Session) -> str:
    """Calcula el nombre de la siguiente versión (v1, v2, ...)."""
    total = db.scalar(select(func.count()).select_from(Modelo)) or 0
    return f"v{int(total) + 1}"


def _conteo_por_clase(etiquetas: list[str]) -> dict[str, int]:
    """Cuenta cuántos ejemplos hay por clase."""
    conteo: dict[str, int] = {}
    for etiqueta in etiquetas:
        conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
    return conteo


def entrenar_nueva_version(
    db: Session, forzar: bool = False, etiquetado_por: str = ""
) -> dict[str, Any]:
    """Entrena una versión nueva (categoría y prioridad) y decide si se activa."""
    inicio = time.perf_counter()
    # Se entrena SOLO con el pool de entrenamiento: nunca con el conjunto de
    # prueba EXTERNO (origen "prueba_externa").
    registros = etiquetas_entrenamiento(db)

    if len(registros) < 8:
        raise ValueError(
            "Se necesitan al menos 8 solicitudes etiquetadas para entrenar el agente."
        )

    ids_fijos, version_prueba = _asegurar_conjunto_prueba(db, registros)
    entrenamiento_regs = [r for r in registros if r["solicitud_id"] not in ids_fijos]
    prueba_regs = [r for r in registros if r["solicitud_id"] in ids_fijos]

    if not entrenamiento_regs:
        entrenamiento_regs, prueba_regs = registros, []

    # Grupos de casi-duplicados calculados sobre TODO el dataset y luego filtrados,
    # para que la validación cruzada del entrenamiento no mezcle variantes iguales.
    grupos_totales = calidad.agrupar_casi_duplicados([r["texto"] for r in registros])
    grupo_por_id = {r["solicitud_id"]: grupos_totales[i] for i, r in enumerate(registros)}
    grupos_train = [grupo_por_id[r["solicitud_id"]] for r in entrenamiento_regs]

    X_train = [r["texto"] for r in entrenamiento_regs]
    y_cat = [r["categoria"] for r in entrenamiento_regs]
    y_pri = [r["prioridad"] for r in entrenamiento_regs]

    clases_categoria = [c["clave"] for c in CATEGORIAS_SEED]

    # 1) Comparación de algoritmos: se calcula UNA sola vez por clasificador y se reutiliza.
    comparacion_cat = entrenamiento.comparar_algoritmos(X_train, y_cat, grupos=grupos_train)
    comparacion_pri = entrenamiento.comparar_algoritmos(X_train, y_pri, grupos=grupos_train)

    # 2) Ajuste de hiperparámetros (GridSearchCV con particiones agrupadas).
    ajuste_cat = entrenamiento.ajustar_hiperparametros(X_train, y_cat, grupos=grupos_train)
    ajuste_pri = entrenamiento.ajustar_hiperparametros(X_train, y_pri, grupos=grupos_train)

    # 3) Entrenamiento del clasificador final con la mejor configuración hallada.
    modelo_cat, _ = entrenamiento.construir_clasificador(
        X_train, y_cat, comparacion=comparacion_cat, config=ajuste_cat.get("mejor")
    )
    modelo_pri, _ = entrenamiento.construir_clasificador(
        X_train, y_pri, comparacion=comparacion_pri, config=ajuste_pri.get("mejor")
    )

    # 4) Métricas reales sobre el conjunto de prueba fijo (o validación cruzada).
    if prueba_regs:
        textos_prueba = [r["texto"] for r in prueba_regs]
        metricas = entrenamiento.evaluar(
            modelo_cat, textos_prueba, [r["categoria"] for r in prueba_regs], clases_categoria
        )
        metricas_pri = entrenamiento.evaluar(
            modelo_pri, textos_prueba, [r["prioridad"] for r in prueba_regs], CLASES_PRIORIDAD
        )
        metodo = "conjunto_prueba_fijo"
        n_prueba = len(prueba_regs)
        n_validacion = 0
    else:
        textos_prueba = []
        metricas = entrenamiento.evaluar_por_validacion_cruzada(
            X_train, y_cat, clases_categoria, comparacion=comparacion_cat
        )
        metricas_pri = entrenamiento.evaluar_por_validacion_cruzada(
            X_train, y_pri, CLASES_PRIORIDAD, comparacion=comparacion_pri
        )
        metodo = "validacion_cruzada"
        n_prueba = 0
        n_validacion = len(X_train)

    # 5) Evaluación ampliada: baselines, calibración, cobertura-precisión y errores.
    baselines_cat = entrenamiento.baselines(
        y_cat, textos_prueba, [r["categoria"] for r in prueba_regs], clases_categoria
    ) if prueba_regs else {}
    baselines_pri = entrenamiento.baselines(
        y_pri, textos_prueba, [r["prioridad"] for r in prueba_regs], CLASES_PRIORIDAD
    ) if prueba_regs else {}
    calibracion = (
        entrenamiento.calibracion_confianza(
            modelo_cat, textos_prueba, [r["categoria"] for r in prueba_regs]
        )
        if prueba_regs
        else {}
    )
    cobertura = (
        entrenamiento.curva_cobertura_precision(
            modelo_cat, textos_prueba, [r["categoria"] for r in prueba_regs]
        )
        if prueba_regs
        else []
    )
    errores = (
        entrenamiento.errores_clasificacion(
            modelo_cat, textos_prueba, [r["categoria"] for r in prueba_regs]
        )
        if prueba_regs
        else []
    )

    # 6) Curva de aprendizaje (reutiliza la comparación ya calculada).
    curva = entrenamiento.curva_de_aprendizaje(
        X_train, y_cat, nombre_algoritmo=comparacion_cat["ganador"], comparacion=comparacion_cat
    )

    # 7) Explicabilidad global: términos más influyentes por clase.
    top_terminos = {
        "categoria": inferencia.terminos_influyentes(modelo_cat, 12),
        "prioridad": inferencia.terminos_influyentes(modelo_pri, 10),
    }

    min_por_clase = min(_conteo_por_clase(y_cat).values(), default=0)
    datos_suficientes = min_por_clase >= entrenamiento.MINIMO_POR_CLASE

    hiperparametros = {
        "vectorizador": ajuste_cat.get("mejor") or {"ngram_range": [1, 2], "min_df": 1},
        "algoritmo_categoria": (ajuste_cat.get("mejor") or {}).get(
            "algoritmo", comparacion_cat["ganador"]
        ),
        "algoritmo_prioridad": (ajuste_pri.get("mejor") or {}).get(
            "algoritmo", comparacion_pri["ganador"]
        ),
        "comparacion_categoria": comparacion_cat["detalle"],
        "comparacion_prioridad": comparacion_pri["detalle"],
        "ajuste_hiperparametros_categoria": ajuste_cat.get("tabla", []),
        "ajuste_hiperparametros_prioridad": ajuste_pri.get("tabla", []),
        "metodo_evaluacion": metodo,
        "version_prueba": version_prueba,
        "umbral_minimo_por_clase": entrenamiento.MINIMO_POR_CLASE,
        "minimo_por_clase_observado": min_por_clase,
    }

    pares = entrenamiento.pares_confundidos(
        metricas.get("matriz_confusion", []), metricas.get("etiquetas_matriz", [])
    )
    pares_pri = entrenamiento.pares_confundidos(
        metricas_pri.get("matriz_confusion", []), metricas_pri.get("etiquetas_matriz", [])
    )

    # 8) Artefacto serializable.
    artefacto = {
        "modelo_categoria": modelo_cat,
        "modelo_prioridad": modelo_pri,
        "clases_categoria": list(modelo_cat.classes_),
        "clases_prioridad": list(modelo_pri.classes_),
        "categorias_info": {
            c["clave"]: {
                "nombre": c["nombre"],
                "departamento": c["departamento"],
                "icono": c["icono"],
            }
            for c in CATEGORIAS_SEED
        },
        "algoritmo_categoria": hiperparametros["algoritmo_categoria"],
        "algoritmo_prioridad": hiperparametros["algoritmo_prioridad"],
        "umbrales_revision": {
            "confianza": settings.umbral_confianza,
            "margen": settings.umbral_margen,
        },
    }
    binario = _serializar(artefacto)

    # 8.1) Eficiencia real de esta versión (Fase A3): tiempo de entrenamiento,
    # tamaño del binario y latencia medida sobre el conjunto de prueba.
    tiempo_entrenamiento_s = time.perf_counter() - inicio
    eficiencia = medir_eficiencia(
        artefacto,
        len(binario),
        prueba_regs or entrenamiento_regs,
        tiempo_entrenamiento_s,
    )

    # 9) Decisión de activación: solo comparable sobre el MISMO conjunto de prueba.
    activo = modelo_activo(db)
    f1_nuevo = float(metricas["f1_macro"])
    # Si la versión activa está contaminada (no comparable), no sirve de baseline:
    # esta versión limpia se activa directamente.
    activo_comparable = activo is not None and bool(activo.valida_para_comparacion)
    if activo is None:
        activar, motivo = True, "Primera versión entrenada: se activa automáticamente."
    elif not activo_comparable:
        activar, motivo = True, (
            f"La versión activa {activo.version} no es comparable "
            f"({activo.motivo_invalidez or 'entrenada con datos del conjunto de prueba'}). "
            f"Se activa esta versión limpia ({f1_nuevo:.4f})."
        )
    elif forzar:
        activar, motivo = True, "Activación forzada por el usuario."
    elif (activo.version_prueba or "") != (version_prueba or ""):
        activar, motivo = False, (
            f"El conjunto de prueba cambió ({activo.version_prueba or 'sin versión'} → "
            f"{version_prueba or 'sin versión'}); las métricas no son comparables. "
            "Reevalúa las versiones o fuerza la activación."
        )
    elif f1_nuevo >= float(activo.f1_macro):
        activar, motivo = True, (
            f"El F1 macro ({f1_nuevo:.4f}) mejora o iguala al de la versión "
            f"{activo.version} ({float(activo.f1_macro):.4f})."
        )
    else:
        activar, motivo = False, (
            f"El F1 macro ({f1_nuevo:.4f}) es inferior al de la versión "
            f"{activo.version} ({float(activo.f1_macro):.4f}); se conserva la activa."
        )

    if activar:
        for otro in db.scalars(select(Modelo).where(Modelo.activo.is_(True))).all():
            otro.activo = False

    matriz = {
        "etiquetas": metricas.get("etiquetas_matriz", []),
        "matriz": metricas.get("matriz_confusion", []),
        "pares_confundidos": pares,
    }

    # Evaluación sobre el conjunto de prueba EXTERNO (nunca usado para entrenar).
    externa = evaluar_en_externo(artefacto, etiquetas_prueba_externa(db))

    evaluacion = {
        "baselines_categoria": baselines_cat,
        "baselines_prioridad": baselines_pri,
        "calibracion_categoria": calibracion,
        "curva_cobertura_precision": cobertura,
        "errores_categoria": errores,
        "casi_duplicados": calidad.detectar_casi_duplicados([r["texto"] for r in registros]),
        "ajuste_hiperparametros_categoria": ajuste_cat,
        "ajuste_hiperparametros_prioridad": ajuste_pri,
        "comparacion_categoria": comparacion_cat,
        "comparacion_prioridad": comparacion_pri,
        "matriz_confusion_prioridad": {
            "etiquetas": metricas_pri.get("etiquetas_matriz", []),
            "matriz": metricas_pri.get("matriz_confusion", []),
            "pares_confundidos": pares_pri,
        },
        "metricas_por_clase_prioridad": metricas_pri.get("metricas_por_clase", {}),
        "umbrales_revision": {
            "confianza": settings.umbral_confianza,
            "margen": settings.umbral_margen,
        },
        "version_prueba": version_prueba,
        "metodo_evaluacion": metodo,
        "n_etiquetas": len(registros),
        "prueba_externa": externa,
    }

    modelo = Modelo(
        version=_siguiente_version(db),
        algoritmo=hiperparametros["algoritmo_categoria"],
        hiperparametros=hiperparametros,
        n_entrenamiento=len(entrenamiento_regs),
        n_validacion=n_validacion,
        n_prueba=n_prueba,
        accuracy=float(metricas["accuracy"]),
        precision_macro=float(metricas["precision_macro"]),
        recall_macro=float(metricas["recall_macro"]),
        f1_macro=f1_nuevo,
        matriz_confusion=matriz,
        metricas_por_clase=metricas["metricas_por_clase"],
        curva_aprendizaje=curva,
        top_terminos=top_terminos,
        version_prueba=version_prueba,
        metodo_evaluacion=metodo,
        accuracy_prioridad=float(metricas_pri["accuracy"]),
        precision_prioridad=float(metricas_pri["precision_macro"]),
        recall_prioridad=float(metricas_pri["recall_macro"]),
        f1_prioridad=float(metricas_pri["f1_macro"]),
        evaluacion=evaluacion,
        # Trazabilidad: ids usados para entrenar (excluyen el conjunto de prueba).
        ids_entrenamiento=sorted(int(r["solicitud_id"]) for r in entrenamiento_regs),
        valida_para_comparacion=True,
        motivo_invalidez="",
        modelo_binario=binario,
        eficiencia=eficiencia,
        activo=activar,
    )
    db.add(modelo)
    db.commit()
    db.refresh(modelo)

    anterior = None
    if activo is not None:
        db.refresh(activo)
        anterior = activo

    _CACHE.pop(modelo.version, None)

    return {
        "activado": activar,
        "motivo": motivo,
        "version_nueva": modelo,
        "version_anterior": anterior,
        "comparacion_algoritmos": {
            "categoria": comparacion_cat["detalle"],
            "prioridad": comparacion_pri["detalle"],
            "ganador_categoria": comparacion_cat["ganador"],
            "ganador_prioridad": comparacion_pri["ganador"],
        },
        "datos_suficientes": bool(datos_suficientes),
        "mensaje": (
            "Entrenamiento completado."
            if datos_suficientes
            else "Datos insuficientes: menos de 30 ejemplos por clase. Los resultados son preliminares."
        ),
        "duracion_ms": round((time.perf_counter() - inicio) * 1000, 2),
        "minimo_por_clase": int(min_por_clase),
    }


def reevaluar_versiones(db: Session, regenerar_prueba: bool = True) -> list[dict[str, Any]]:
    """Reevalúa las versiones COMPARABLES sobre el conjunto de prueba fijo actual.

    Solo se recalculan métricas de las versiones cuyo `ids_entrenamiento` NO
    intersecta con el conjunto de prueba fijo (evita la fuga de datos). Las demás
    se marcan `valida_para_comparacion=false` con su motivo y conservan sus datos
    históricos, pero no se muestran en la evolución ni pueden activarse sin forzar.
    """
    registros = etiquetas_entrenamiento(db)
    if len(registros) < MINIMO_PARA_FIJO:
        return []

    if regenerar_prueba:
        ids_fijos, version_prueba = regenerar_conjunto_prueba(db, registros)
    else:
        ids_fijos, version_prueba = _asegurar_conjunto_prueba(db, registros)

    prueba_regs = [r for r in registros if r["solicitud_id"] in ids_fijos]
    if not prueba_regs:
        return []

    # Pool de entrenamiento disponible = dataset (sin externo) menos la prueba fija.
    tamano_pool = max(0, len(registros) - len(ids_fijos))
    registros_externos = etiquetas_prueba_externa(db)

    textos_prueba = [r["texto"] for r in prueba_regs]
    y_cat = [r["categoria"] for r in prueba_regs]
    y_pri = [r["prioridad"] for r in prueba_regs]
    clases_categoria = [c["clave"] for c in CATEGORIAS_SEED]

    actualizados: list[dict[str, Any]] = []
    for modelo in db.scalars(select(Modelo)).all():
        valida, motivo = version_valida_para_comparacion(modelo, ids_fijos, tamano_pool)
        modelo.valida_para_comparacion = valida
        modelo.motivo_invalidez = motivo
        if not valida:
            # No se recalcula nada: la versión queda fuera de la comparación.
            continue

        try:
            artefacto = deserializar(modelo)
        except Exception:  # pragma: no cover - binario corrupto
            continue

        metricas = entrenamiento.evaluar(artefacto["modelo_categoria"], textos_prueba, y_cat, clases_categoria)
        metricas_pri = entrenamiento.evaluar(artefacto["modelo_prioridad"], textos_prueba, y_pri, CLASES_PRIORIDAD)

        modelo.accuracy = float(metricas["accuracy"])
        modelo.precision_macro = float(metricas["precision_macro"])
        modelo.recall_macro = float(metricas["recall_macro"])
        modelo.f1_macro = float(metricas["f1_macro"])
        modelo.metricas_por_clase = metricas["metricas_por_clase"]
        modelo.matriz_confusion = {
            "etiquetas": metricas.get("etiquetas_matriz", []),
            "matriz": metricas.get("matriz_confusion", []),
            "pares_confundidos": entrenamiento.pares_confundidos(
                metricas.get("matriz_confusion", []), metricas.get("etiquetas_matriz", [])
            ),
        }
        modelo.accuracy_prioridad = float(metricas_pri["accuracy"])
        modelo.precision_prioridad = float(metricas_pri["precision_macro"])
        modelo.recall_prioridad = float(metricas_pri["recall_macro"])
        modelo.f1_prioridad = float(metricas_pri["f1_macro"])
        modelo.version_prueba = version_prueba
        modelo.n_prueba = len(prueba_regs)
        # La reevaluación siempre se hace sobre el conjunto de prueba fijo, por lo
        # que el método de evaluación queda registrado también a nivel de columna
        # (algunas versiones antiguas lo tenían vacío).
        modelo.metodo_evaluacion = "conjunto_prueba_fijo"

        evaluacion = dict(modelo.evaluacion or {})
        evaluacion.update(
            {
                "baselines_categoria": entrenamiento.baselines(
                    y_cat, textos_prueba, y_cat, clases_categoria
                ),
                "baselines_prioridad": entrenamiento.baselines(y_pri, textos_prueba, y_pri, CLASES_PRIORIDAD),
                "calibracion_categoria": entrenamiento.calibracion_confianza(
                    artefacto["modelo_categoria"], textos_prueba, y_cat
                ),
                "curva_cobertura_precision": entrenamiento.curva_cobertura_precision(
                    artefacto["modelo_categoria"], textos_prueba, y_cat
                ),
                "errores_categoria": entrenamiento.errores_clasificacion(
                    artefacto["modelo_categoria"], textos_prueba, y_cat
                ),
                "comparacion_categoria": entrenamiento.comparar_algoritmos(
                    [r["texto"] for r in registros], [r["categoria"] for r in registros]
                ),
                "matriz_confusion_prioridad": {
                    "etiquetas": metricas_pri.get("etiquetas_matriz", []),
                    "matriz": metricas_pri.get("matriz_confusion", []),
                    "pares_confundidos": entrenamiento.pares_confundidos(
                        metricas_pri.get("matriz_confusion", []), metricas_pri.get("etiquetas_matriz", [])
                    ),
                },
                "metricas_por_clase_prioridad": metricas_pri.get("metricas_por_clase", {}),
                "version_prueba": version_prueba,
                "metodo_evaluacion": "conjunto_prueba_fijo",
                "n_etiquetas": len(registros),
                "prueba_externa": evaluar_en_externo(artefacto, registros_externos),
            }
        )
        modelo.evaluacion = evaluacion
        actualizados.append({"version": modelo.version, "f1_macro": modelo.f1_macro})

    db.commit()
    return actualizados


# ---------------------------------------------------------------------------
# Predicción con el modelo activo
# ---------------------------------------------------------------------------


def predecir_texto(db: Session, texto: str) -> dict[str, Any] | None:
    """Predice categoría y prioridad con el modelo activo.

    Marca `requiere_revision` cuando la confianza o el margen quedan por debajo de
    los umbrales configurados (el caso se deriva a revisión humana).
    Devuelve `None` si todavía no existe un modelo entrenado.
    """
    modelo = modelo_activo(db)
    if modelo is None:
        return None

    artefacto = deserializar(modelo)
    umbrales = artefacto.get("umbrales_revision") or {
        "confianza": settings.umbral_confianza,
        "margen": settings.umbral_margen,
    }
    inicio = time.perf_counter()
    resultado = inferencia.predecir_solicitud(
        artefacto["modelo_categoria"], artefacto["modelo_prioridad"], texto
    )
    latencia = (time.perf_counter() - inicio) * 1000

    requiere_revision = bool(
        resultado["confianza"] < umbrales["confianza"]
        or resultado["margen"] < umbrales["margen"]
    )

    info = artefacto["categorias_info"].get(resultado["categoria"], {})
    contribuciones = inferencia.contribuciones_documento(
        artefacto["modelo_categoria"], texto, resultado["categoria"], top_n=8
    )

    return {
        **resultado,
        "categoria_nombre": info.get("nombre", resultado["categoria"]),
        "departamento": info.get("departamento", ""),
        "icono": info.get("icono", "grid"),
        "version_modelo": modelo.version,
        "algoritmo": artefacto.get("algoritmo_categoria", modelo.algoritmo),
        "latencia_ms": round(latencia, 2),
        "contribuciones": contribuciones,
        "requiere_revision": requiere_revision,
        "umbral_confianza": umbrales["confianza"],
        "umbral_margen": umbrales["margen"],
    }


def predecir_con_explicacion(db: Session, texto: str) -> dict[str, Any] | None:
    """Agrega los datos de tokenización y la TRAZA completa (Fase A1) a la predicción.

    Se añaden las 11 etapas reales del agente: texto original, normalizado, tokens,
    tokens sin stopwords, n-gramas, términos TF-IDF, puntajes de decisión por clase,
    probabilidades calibradas, margen, comparación con los umbrales y la decisión
    final, más el resumen equivalente para la prioridad.
    """
    prediccion = predecir_texto(db, texto)
    if prediccion is None:
        return None

    modelo = modelo_activo(db)
    traza: dict[str, Any] | None = None
    if modelo is not None:
        artefacto = deserializar(modelo)
        umbrales = artefacto.get("umbrales_revision") or {
            "confianza": settings.umbral_confianza,
            "margen": settings.umbral_margen,
        }
        traza = inferencia.construir_traza(
            artefacto["modelo_categoria"],
            artefacto["modelo_prioridad"],
            texto,
            umbrales,
        )

    originales = _PALABRAS.findall(texto)
    return {
        **prediccion,
        "texto": texto,
        "texto_normalizado": normalizar(texto),
        "tokens": tokenizar(texto),
        "tokens_originales": originales,
        "stopwords": sum(1 for palabra in originales if normalizar(palabra) in STOPWORDS),
        "traza": traza,
    }


# ---------------------------------------------------------------------------
# Parámetros del modelo activo (Fase A2)
# ---------------------------------------------------------------------------


def _hiperparametros_clasificador(modelo: Any) -> dict[str, Any]:
    """Extrae los hiperparámetros reales del clasificador final del pipeline.

    Se admite tanto un clasificador directo como uno calibrado
    (`CalibratedClassifierCV`, cuyo estimador base guarda C/class_weight).
    """
    clasificador = modelo.named_steps["clf"]
    base = getattr(clasificador, "estimator", clasificador)
    return {
        "C": getattr(base, "C", None),
        "alpha": getattr(base, "alpha", None),
        "class_weight": getattr(base, "class_weight", None),
        "max_iter": getattr(base, "max_iter", None),
        "calibrado": hasattr(clasificador, "calibrated_classifiers_"),
    }


def parametros_modelo_activo(db: Session) -> dict[str, Any] | None:
    """Parámetros completos del modelo activo para la interfaz y el informe (A2).

    Todo se lee del binario real (vectorizadores y clasificadores) y de la fila del
    modelo: no se inventa ningún valor.
    """
    modelo = modelo_activo(db)
    if modelo is None:
        return None

    artefacto = deserializar(modelo)
    modelo_cat = artefacto["modelo_categoria"]
    modelo_pri = artefacto["modelo_prioridad"]
    vec_cat = modelo_cat.named_steps["tfidf"]
    vec_pri = modelo_pri.named_steps["tfidf"]
    hiper = modelo.hiperparametros or {}

    n_train = len(modelo.ids_entrenamiento or []) or int(modelo.n_entrenamiento or 0)
    n_prueba = int(modelo.n_prueba or modelo.n_validacion or 0)
    n_externa = len(etiquetas_prueba_externa(db))
    total_fijo = n_train + n_prueba

    return {
        "version": modelo.version,
        "fecha": modelo.fecha,
        "algoritmo_categoria": artefacto.get("algoritmo_categoria") or modelo.algoritmo,
        "algoritmo_prioridad": artefacto.get("algoritmo_prioridad", ""),
        "hiperparametros": {
            "vectorizador": hiper.get("vectorizador", {}),
            "categoria": _hiperparametros_clasificador(modelo_cat),
            "prioridad": _hiperparametros_clasificador(modelo_pri),
        },
        "tfidf": {
            "n_caracteristicas": int(len(vec_cat.get_feature_names_out())),
            "tamano_vocabulario": int(len(vec_cat.vocabulary_)),
            "ngram_range": [int(vec_cat.ngram_range[0]), int(vec_cat.ngram_range[1])],
            "min_df": int(vec_cat.min_df),
            "sublinear_tf": bool(vec_cat.sublinear_tf),
            "n_caracteristicas_prioridad": int(len(vec_pri.get_feature_names_out())),
        },
        "division": {
            "esquema": (
                "entrenamiento + conjunto de prueba fijo reservado por grupos de "
                "casi-duplicados (comparabilidad entre versiones)"
            ),
            "semilla": 42,
            "entrenamiento": n_train,
            "prueba_fija": n_prueba,
            "prueba_externa": n_externa,
            "proporcion_entrenamiento": (
                round(n_train / total_fijo, 4) if total_fijo else None
            ),
            "proporcion_prueba": round(n_prueba / total_fijo, 4) if total_fijo else None,
            "folds_max": 5,
            "validacion_cruzada": (
                "StratifiedGroupKFold / StratifiedKFold agrupada por casi-duplicados"
            ),
        },
        "umbrales": {
            "confianza": settings.umbral_confianza,
            "margen": settings.umbral_margen,
        },
        "n_entrenamiento": n_train,
        "n_prueba_fija": n_prueba,
        "n_prueba_externa": n_externa,
        "version_prueba": modelo.version_prueba,
        "metodo_evaluacion": modelo.metodo_evaluacion,
        "comparacion_algoritmos": {
            "ganador_categoria": hiper.get("algoritmo_categoria", modelo.algoritmo),
            "ganador_prioridad": hiper.get("algoritmo_prioridad", ""),
            "categoria": hiper.get("comparacion_categoria", {}),
            "prioridad": hiper.get("comparacion_prioridad", {}),
        },
        "eficiencia": modelo.eficiencia or {},
    }
