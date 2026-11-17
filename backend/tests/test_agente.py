"""Pruebas de la trazabilidad del agente, los parámetros y el informe del agente.

Cubren lo añadido en las Fases A y B:
  * la traza didáctica de 11 etapas (`ml.inferencia.construir_traza`),
  * el endpoint de parámetros del modelo activo (`GET /api/modelo/parametros`),
  * la traza devuelta por `POST /api/predecir`,
  * el informe del agente (.md/.json/.zip) y sus helpers.
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Informe
from app.servicio_informe import (
    construir_zip,
    generar_y_guardar,
    nombre_archivo,
    render_ejemplos_proceso,
)
from app.servicio_modelo import entrenar_nueva_version
from ml.entrenamiento import construir_clasificador
from ml.inferencia import construir_traza
from tests.conftest import crear_dataset_etiquetado

UMBRALES = {"confianza": 60.0, "margen": 15.0}

# Conjuntos sintéticos: cada categoría/prioridad con vocabulario propio y claro.
TEXTOS_CAT = (
    ["fuga de agua potable tuberia rota"] * 6
    + ["basura acumulada contenedor lleno"] * 6
    + ["poste de luz apagado alumbrado"] * 6
)
ETIQUETAS_CAT = ["agua"] * 6 + ["limpieza"] * 6 + ["alumbrado"] * 6

TEXTOS_PRI = (
    ["emergencia riesgo personas inmediato"] * 6
    + ["afecta el servicio hace dias"] * 6
    + ["mantenimiento menor sin urgencia"] * 6
)
ETIQUETAS_PRI = ["ALTA"] * 6 + ["MEDIA"] * 6 + ["BAJA"] * 6

CLAVES_TRAZA = {
    "texto_original",
    "texto_normalizado",
    "tokens",
    "tokens_sin_stopwords",
    "stopwords_eliminadas",
    "n_gramas",
    "terminos_tfidf",
    "puntajes_categoria",
    "probabilidades_categoria",
    "confianza_categoria",
    "margen_categoria",
    "decision",
    "prioridad",
}


def _cabeceras() -> dict[str, str]:
    """Cabecera X-API-Key cuando el backend tiene configurada una clave."""
    return {"X-API-Key": settings.api_key} if settings.api_key else {}


# ---------------------------------------------------------------------------
# Traza del agente (sin base de datos)
# ---------------------------------------------------------------------------


def test_construir_traza_tiene_las_11_etapas() -> None:
    modelo_cat, _ = construir_clasificador(TEXTOS_CAT, ETIQUETAS_CAT)
    modelo_pri, _ = construir_clasificador(TEXTOS_PRI, ETIQUETAS_PRI)
    texto = "Hay una fuga de agua potable en la esquina"

    traza = construir_traza(modelo_cat, modelo_pri, texto, UMBRALES)

    # La traza expone exactamente las claves que consume la interfaz.
    assert set(traza) == CLAVES_TRAZA

    # Etapas 1-2: el original se conserva y el normalizado va en minúsculas sin tildes.
    assert traza["texto_original"] == texto
    assert traza["texto_normalizado"] == traza["texto_normalizado"].lower()
    assert "á" not in traza["texto_normalizado"] and "é" not in traza["texto_normalizado"]

    # Etapa 3: tokens en minúsculas. Etapa 4: sin stopwords ⊆ tokens.
    assert traza["tokens"] and all(t == t.lower() for t in traza["tokens"])
    assert set(traza["tokens_sin_stopwords"]) <= set(traza["tokens"])

    # Etapa 5: n-gramas generados por el analizador del vectorizador.
    assert traza["n_gramas"]

    # Etapa 6: cada término lleva su tf, su idf real y su peso TF-IDF.
    assert traza["terminos_tfidf"]
    for termino in traza["terminos_tfidf"]:
        assert {"termino", "tf", "idf", "tfidf"} <= set(termino)
        assert termino["tfidf"] > 0 and termino["idf"] > 0

    # Etapa 7: un puntaje por clase válida. Etapa 8: probabilidades calibradas ≈ 1.
    assert traza["puntajes_categoria"]
    assert {p["clase"] for p in traza["puntajes_categoria"]} <= set(modelo_cat.classes_)
    suma = sum(p["probabilidad"] for p in traza["probabilidades_categoria"])
    assert abs(suma - 1.0) < 0.05

    # Etapas 9-10: margen, umbrales y decisión final coherentes.
    decision = traza["decision"]
    assert decision["umbral_confianza"] == 60.0
    assert decision["umbral_margen"] == 15.0
    assert decision["resultado"] in {"automatica", "revision_humana"}
    assert decision["categoria"] in set(modelo_cat.classes_)
    esperado = (
        "automatica"
        if decision["cumple_confianza"] and decision["cumple_margen"]
        else "revision_humana"
    )
    assert decision["resultado"] == esperado

    # Etapa 11: resumen equivalente para la prioridad.
    assert traza["prioridad"]["clase"] in set(modelo_pri.classes_)
    assert traza["prioridad"]["probabilidades"]


# ---------------------------------------------------------------------------
# Parámetros y traza del modelo activo (API)
# ---------------------------------------------------------------------------


def test_parametros_y_traza_del_modelo_activo(db: Session, client: TestClient) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)
    entrenar_nueva_version(db, forzar=True)

    respuesta = client.get("/api/modelo/parametros")
    assert respuesta.status_code == 200
    parametros = respuesta.json()
    for clave in (
        "version",
        "algoritmo_categoria",
        "algoritmo_prioridad",
        "hiperparametros",
        "tfidf",
        "division",
        "umbrales",
        "eficiencia",
        "comparacion_algoritmos",
    ):
        assert clave in parametros
    assert parametros["tfidf"]["n_caracteristicas"] > 0
    assert parametros["tfidf"]["ngram_range"][0] >= 1
    assert parametros["umbrales"]["confianza"] == settings.umbral_confianza
    assert parametros["umbrales"]["margen"] == settings.umbral_margen
    assert parametros["division"]["entrenamiento"] > 0

    prediccion = client.post("/api/predecir", json={"texto": "Hay una fuga de agua potable"})
    assert prediccion.status_code == 200
    cuerpo = prediccion.json()
    assert cuerpo["traza"] is not None
    assert set(cuerpo["traza"]) == CLAVES_TRAZA
    assert cuerpo["traza"]["texto_original"] == "Hay una fuga de agua potable"
    assert cuerpo["traza"]["probabilidades_categoria"]
    assert cuerpo["version_modelo"]


# ---------------------------------------------------------------------------
# Informe del agente: helpers puros
# ---------------------------------------------------------------------------


def _informe_de_prueba() -> Informe:
    """Informe en memoria para probar los helpers sin base de datos."""
    return Informe(
        version_modelo="vtest",
        generado_por="Pruebas",
        estado="completado",
        contenido_md="# Informe de prueba\n\nContenido de ejemplo.",
        contenido_json={
            "cabecera": {
                "nombre_archivo": "informe_agente_vtest_2026-01-01",
                "version_modelo": "vtest",
                "hash_datos": "abc123",
                "fecha_generacion": "2026-01-01T00:00:00",
            },
            "matrices_confusion": {
                "categoria": {
                    "etiquetas": ["agua", "calles"],
                    "absoluta": [[2, 1], [0, 3]],
                    "normalizada": [[0.66, 0.33], [0.0, 1.0]],
                },
                "prioridad": {
                    "etiquetas": ["ALTA", "BAJA"],
                    "absoluta": [[1, 0], [0, 2]],
                    "normalizada": [[1.0, 0.0], [0.0, 1.0]],
                },
            },
            "ejemplos_proceso": [],
        },
    )


def test_nombre_archivo_usa_la_cabecera() -> None:
    informe = _informe_de_prueba()
    assert nombre_archivo(informe, "md") == "informe_agente_vtest_2026-01-01.md"
    assert nombre_archivo(informe, "json").endswith(".json")
    assert nombre_archivo(informe, "zip").endswith(".zip")


def test_construir_zip_incluye_markdown_json_y_csv() -> None:
    contenido = construir_zip(_informe_de_prueba())
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        nombres = set(archivo.namelist())

    assert "informe_agente_vtest_2026-01-01.md" in nombres
    assert "informe_agente_vtest_2026-01-01.json" in nombres
    assert "matriz_confusion_categoria.csv" in nombres
    assert "matriz_confusion_categoria_normalizada.csv" in nombres
    assert "matriz_confusion_prioridad.csv" in nombres


def test_render_ejemplos_proceso_encabeza_con_la_version() -> None:
    texto = render_ejemplos_proceso(_informe_de_prueba().contenido_json)
    assert texto.startswith("# Ejemplo de proceso del agente")
    assert "vtest" in texto and "abc123" in texto


# ---------------------------------------------------------------------------
# Informe del agente: endpoints
# ---------------------------------------------------------------------------


def test_endpoints_del_informe(db: Session, client: TestClient) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)
    entrenar_nueva_version(db, forzar=True)

    generado = client.post(
        "/api/informe/generar", json={"generado_por": "Pruebas"}, headers=_cabeceras()
    )
    assert generado.status_code == 200
    cuerpo = generado.json()
    assert cuerpo["estado"] == "completado"
    informe_id = cuerpo["id"]

    historial = client.get("/api/informe", headers=_cabeceras())
    assert historial.status_code == 200
    assert any(fila["id"] == informe_id for fila in historial.json())

    detalle = client.get(f"/api/informe/{informe_id}", headers=_cabeceras())
    assert detalle.status_code == 200
    datos = detalle.json()
    assert datos["contenido_md"]
    for clave in ("cabecera", "calidad", "parametros", "librerias", "matrices_confusion"):
        assert clave in datos["contenido_json"]

    for formato, media in (
        ("md", "text/markdown"),
        ("json", "application/json"),
        ("zip", "application/zip"),
    ):
        descarga = client.get(
            f"/api/informe/{informe_id}/descargar",
            params={"formato": formato},
            headers=_cabeceras(),
        )
        assert descarga.status_code == 200
        assert media in descarga.headers["content-type"]
        assert descarga.content

    # Formato no permitido → validación del patrón de la query.
    invalido = client.get(
        f"/api/informe/{informe_id}/descargar", params={"formato": "pdf"}, headers=_cabeceras()
    )
    assert invalido.status_code == 422

    # Informe inexistente → 404.
    assert client.get("/api/informe/99999999", headers=_cabeceras()).status_code == 404


def test_generar_y_guardar_persiste_el_contenido(db: Session) -> None:
    crear_dataset_etiquetado(db, por_categoria=5)
    entrenar_nueva_version(db, forzar=True)

    informe = generar_y_guardar(db, {"generado_por": "Pruebas"})

    assert informe.estado == "completado"
    assert informe.version_modelo
    assert informe.contenido_md.startswith("# ")
    assert informe.contenido_json.get("cabecera", {}).get("version_modelo")
