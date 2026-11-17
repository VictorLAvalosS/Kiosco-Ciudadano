"""Funciones para convertir modelos ORM en diccionarios listos para la API."""

from __future__ import annotations

from typing import Any

from app.models import Etiqueta, Modelo, Solicitud


def serializar_etiqueta(etiqueta: Etiqueta | None) -> dict[str, Any] | None:
    """Convierte una etiqueta ORM en un diccionario."""
    if etiqueta is None:
        return None
    categoria = etiqueta.categoria
    return {
        "id": etiqueta.id,
        "categoria_id": etiqueta.categoria_id,
        "categoria_clave": categoria.clave if categoria else "",
        "categoria_nombre": categoria.nombre if categoria else "",
        "prioridad": etiqueta.prioridad,
        "etiquetado_por": etiqueta.etiquetado_por,
        "fecha": etiqueta.fecha,
        "vigente": etiqueta.vigente,
    }


def serializar_solicitud(
    solicitud: Solicitud,
    etiqueta: Etiqueta | None = None,
    prediccion_detalle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convierte una solicitud ORM (con su predicción) en un diccionario."""
    categoria_predicha = solicitud.categoria_predicha
    probabilidades = solicitud.probabilidades
    if isinstance(probabilidades, dict):
        probabilidades = probabilidades.get("ranking", [])
    return {
        "id": solicitud.id,
        "ticket": solicitud.ticket,
        "texto": solicitud.texto,
        "otb": solicitud.otb,
        "zona": solicitud.zona,
        "fecha": solicitud.fecha,
        "estado": solicitud.estado,
        "origen": solicitud.origen,
        "categoria_predicha_id": solicitud.categoria_predicha_id,
        "categoria_predicha_clave": categoria_predicha.clave if categoria_predicha else None,
        "categoria_predicha_nombre": categoria_predicha.nombre if categoria_predicha else None,
        "categoria_predicha_departamento": (
            categoria_predicha.departamento if categoria_predicha else None
        ),
        "categoria_predicha_icono": categoria_predicha.icono if categoria_predicha else None,
        "prioridad_predicha": solicitud.prioridad_predicha,
        "confianza": solicitud.confianza,
        "probabilidades": probabilidades,
        "version_modelo": solicitud.version_modelo,
        "latencia_ms": solicitud.latencia_ms,
        "requiere_revision": bool(solicitud.requiere_revision),
        "prediccion_detalle": prediccion_detalle,
        "etiquetada": etiqueta is not None,
        "etiqueta": serializar_etiqueta(etiqueta),
    }


def serializar_modelo(modelo: Modelo) -> dict[str, Any]:
    """Convierte una versión del modelo en un diccionario (sin el binario)."""
    return {
        "id": modelo.id,
        "version": modelo.version,
        "fecha": modelo.fecha,
        "algoritmo": modelo.algoritmo,
        "hiperparametros": modelo.hiperparametros,
        "n_entrenamiento": modelo.n_entrenamiento,
        "n_validacion": modelo.n_validacion,
        "n_prueba": modelo.n_prueba,
        "accuracy": modelo.accuracy,
        "precision_macro": modelo.precision_macro,
        "recall_macro": modelo.recall_macro,
        "f1_macro": modelo.f1_macro,
        "matriz_confusion": modelo.matriz_confusion,
        "metricas_por_clase": modelo.metricas_por_clase,
        "curva_aprendizaje": modelo.curva_aprendizaje,
        "top_terminos": modelo.top_terminos,
        "version_prueba": modelo.version_prueba,
        "metodo_evaluacion": modelo.metodo_evaluacion,
        "accuracy_prioridad": modelo.accuracy_prioridad,
        "precision_prioridad": modelo.precision_prioridad,
        "recall_prioridad": modelo.recall_prioridad,
        "f1_prioridad": modelo.f1_prioridad,
        "evaluacion": modelo.evaluacion,
        # Trazabilidad: nº de ids usados al entrenar (no se exponen todos para no
        # inflar la respuesta) y si la versión es comparable o no.
        "n_ids_entrenamiento": len(modelo.ids_entrenamiento or []),
        "valida_para_comparacion": bool(modelo.valida_para_comparacion),
        "motivo_invalidez": modelo.motivo_invalidez or "",
        "eficiencia": modelo.eficiencia or {},
        "activo": modelo.activo,
    }
