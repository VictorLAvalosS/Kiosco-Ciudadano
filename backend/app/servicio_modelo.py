"""Servicio de entrenamiento, versionado y activación del modelo.

Reglas de negocio clave:
  * Se entrena con TODAS las etiquetas vigentes, excluyendo siempre el conjunto
    de prueba fijo (para que las versiones sean comparables).
  * Una versión nueva solo se activa si su F1 macro en el conjunto fijo mejora
    o iguala al de la versión activa (salvo que el usuario fuerce la activación).
  * El binario serializado (joblib) se guarda en la propia base de datos, de modo
    que todo el equipo trabaja con el mismo modelo.
"""

from __future__ import annotations

import io
import re
import time
from typing import Any

import joblib
from sklearn.model_selection import StratifiedShuffleSplit
from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from app.categorias import CATEGORIAS_SEED
from app.models import ConjuntoPruebaFijo, Etiqueta, Modelo, Solicitud
from ml import entrenamiento, inferencia
from ml.preprocesamiento import STOPWORDS, normalizar, tokenizar

# Caché en memoria de los modelos deserializados (por versión).
_CACHE: dict[str, dict[str, Any]] = {}

# Mínimo de ejemplos etiquetados para reservar un conjunto de prueba fijo.
MINIMO_PARA_FIJO = 40
# Proporción reservada para el conjunto de prueba fijo.
PROPORCION_PRUEBA = 0.2

CLASES_PRIORIDAD = ["ALTA", "MEDIA", "BAJA"]
_PALABRAS = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------


def etiquetas_vigentes(db: Session) -> list[dict[str, Any]]:
    """Devuelve todas las etiquetas vigentes junto al texto de su solicitud."""
    filas = db.execute(
        select(Solicitud.id, Solicitud.texto, Etiqueta.prioridad, Etiqueta.categoria_id)
        .join(Etiqueta, Etiqueta.solicitud_id == Solicitud.id)
        .where(Etiqueta.vigente.is_(True))
    ).all()

    from app.models import Categoria

    mapa = {c.id: c.clave for c in db.scalars(select(Categoria)).all()}
    return [
        {
            "solicitud_id": int(fila[0]),
            "texto": fila[1],
            "prioridad": fila[2],
            "categoria": mapa.get(fila[3], "otras"),
        }
        for fila in filas
    ]


def _asegurar_conjunto_prueba(db: Session, registros: list[dict[str, Any]]) -> set[int]:
    """Reserva (una sola vez) un conjunto de prueba fijo y estratificado."""
    existentes = set(db.scalars(select(ConjuntoPruebaFijo.solicitud_id)).all())
    if existentes:
        return existentes

    if len(registros) < MINIMO_PARA_FIJO:
        return set()

    claves = [r["categoria"] for r in registros]
    ids: set[int] = set()
    try:
        divisor = StratifiedShuffleSplit(
            n_splits=1, test_size=PROPORCION_PRUEBA, random_state=42
        )
        _, prueba = next(divisor.split([[0]] * len(claves), claves))
        ids = {registros[int(i)]["solicitud_id"] for i in prueba}
    except Exception:
        # Si no es posible estratificar (clases con muy pocos miembros), no se reserva.
        return set()

    for solicitud_id in ids:
        db.add(ConjuntoPruebaFijo(solicitud_id=solicitud_id))
    db.commit()
    return ids


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
# Entrenamiento
# ---------------------------------------------------------------------------


def _siguiente_version(db: Session) -> str:
    """Calcula el nombre de la siguiente versión (v1, v2, ...)."""
    total = db.scalar(select(func.count()).select_from(Modelo)) or 0
    return f"v{int(total) + 1}"


def entrenar_nueva_version(
    db: Session, forzar: bool = False, etiquetado_por: str = ""
) -> dict[str, Any]:
    """Entrena una versión nueva y decide si se activa."""
    inicio = time.perf_counter()
    registros = etiquetas_vigentes(db)

    if len(registros) < 8:
        raise ValueError(
            "Se necesitan al menos 8 solicitudes etiquetadas para entrenar el agente."
        )

    ids_fijos = _asegurar_conjunto_prueba(db, registros)
    entrenamiento_regs = [r for r in registros if r["solicitud_id"] not in ids_fijos]
    prueba_regs = [r for r in registros if r["solicitud_id"] in ids_fijos]

    if not entrenamiento_regs:
        entrenamiento_regs, prueba_regs = registros, []

    X_train = [r["texto"] for r in entrenamiento_regs]
    y_cat = [r["categoria"] for r in entrenamiento_regs]
    y_pri = [r["prioridad"] for r in entrenamiento_regs]

    clases_categoria = [c["clave"] for c in CATEGORIAS_SEED]

    # 1) Comparación de algoritmos y entrenamiento del clasificador de categoría.
    modelo_cat, comparacion_cat = entrenamiento.construir_clasificador(X_train, y_cat)

    # 2) Clasificador de prioridad con la misma técnica.
    modelo_pri, comparacion_pri = entrenamiento.construir_clasificador(X_train, y_pri)

    # 3) Métricas reales sobre el conjunto de prueba fijo (o validación cruzada).
    if prueba_regs:
        metricas = entrenamiento.evaluar(
            modelo_cat,
            [r["texto"] for r in prueba_regs],
            [r["categoria"] for r in prueba_regs],
            clases_categoria,
        )
        metodo = "conjunto_prueba_fijo"
        n_prueba = len(prueba_regs)
        n_validacion = 0
    else:
        metricas = entrenamiento.evaluar_por_validacion_cruzada(X_train, y_cat, clases_categoria)
        metodo = "validacion_cruzada"
        n_prueba = 0
        n_validacion = len(X_train)

    # 4) Curva de aprendizaje real.
    curva = entrenamiento.curva_de_aprendizaje(X_train, y_cat)

    # 5) Explicabilidad global: términos más influyentes por clase.
    top_terminos = {
        "categoria": inferencia.terminos_influyentes(modelo_cat, 12),
        "prioridad": inferencia.terminos_influyentes(modelo_pri, 10),
    }

    minimo_por_clase = min(
        (p["soporte"] for p in metricas["metricas_por_clase"].values()),
        default=0,
    )
    datos_suficientes = min(_conteo_por_clase(y_cat).values(), default=0) >= entrenamiento.MINIMO_POR_CLASE

    hiperparametros = {
        "vectorizador": {"ngram_range": [1, 2], "sublinear_tf": True, "min_df": 1},
        "algoritmo_categoria": comparacion_cat["ganador"],
        "algoritmo_prioridad": comparacion_pri["ganador"],
        "comparacion_categoria": comparacion_cat["detalle"],
        "comparacion_prioridad": comparacion_pri["detalle"],
        "metodo_evaluacion": metodo,
        "umbral_minimo_por_clase": entrenamiento.MINIMO_POR_CLASE,
        "minimo_por_clase_observado": min(_conteo_por_clase(y_cat).values(), default=0),
    }

    pares = entrenamiento.pares_confundidos(
        metricas.get("matriz_confusion", []), metricas.get("etiquetas_matriz", [])
    )

    # 6) Artefacto serializable.
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
        "algoritmo_categoria": comparacion_cat["ganador"],
        "algoritmo_prioridad": comparacion_pri["ganador"],
    }
    binario = _serializar(artefacto)

    # 7) Decisión de activación comparando con la versión activa.
    activo = modelo_activo(db)
    f1_nuevo = float(metricas["f1_macro"])
    if activo is None:
        activar, motivo = True, "Primera versión entrenada: se activa automáticamente."
    elif forzar:
        activar, motivo = True, "Activación forzada por el usuario."
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

    modelo = Modelo(
        version=_siguiente_version(db),
        algoritmo=comparacion_cat["ganador"],
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
        modelo_binario=binario,
        activo=activar,
    )
    db.add(modelo)
    db.commit()
    db.refresh(modelo)

    # La versión anterior se relee para devolver la comparación actualizada.
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
        "minimo_por_clase": int(minimo_por_clase),
    }


def _conteo_por_clase(etiquetas: list[str]) -> dict[str, int]:
    """Cuenta cuántos ejemplos hay por clase."""
    conteo: dict[str, int] = {}
    for etiqueta in etiquetas:
        conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
    return conteo


# ---------------------------------------------------------------------------
# Predicción con el modelo activo
# ---------------------------------------------------------------------------


def predecir_texto(db: Session, texto: str) -> dict[str, Any] | None:
    """Predice categoría y prioridad con el modelo activo.

    Devuelve `None` si todavía no existe un modelo entrenado.
    """
    modelo = modelo_activo(db)
    if modelo is None:
        return None

    artefacto = deserializar(modelo)
    inicio = time.perf_counter()
    resultado = inferencia.predecir_solicitud(
        artefacto["modelo_categoria"], artefacto["modelo_prioridad"], texto
    )
    latencia = (time.perf_counter() - inicio) * 1000

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
    }


def predecir_con_explicacion(db: Session, texto: str) -> dict[str, Any] | None:
    """Agrega los datos de tokenización a una predicción del modelo activo."""
    prediccion = predecir_texto(db, texto)
    if prediccion is None:
        return None

    originales = _PALABRAS.findall(texto)
    return {
        **prediccion,
        "texto": texto,
        "texto_normalizado": normalizar(texto),
        "tokens": tokenizar(texto),
        "tokens_originales": originales,
        "stopwords": sum(1 for palabra in originales if normalizar(palabra) in STOPWORDS),
    }
