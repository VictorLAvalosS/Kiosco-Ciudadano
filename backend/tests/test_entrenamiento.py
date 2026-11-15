"""Pruebas del módulo de entrenamiento (scikit-learn, sin base de datos)."""

from __future__ import annotations

from ml.entrenamiento import (
    comparar_algoritmos,
    construir_clasificador,
    curva_de_aprendizaje,
    evaluar,
    evaluar_por_validacion_cruzada,
    pares_confundidos,
)

# Dataset sintético pequeño: 3 categorías claramente diferenciadas.
TEXTOS = (
    ["fuga de agua potable tuberia rota"] * 6
    + ["basura acumulada contenedor lleno"] * 6
    + ["poste de luz apagado alumbrado"] * 6
)
ETIQUETAS = ["agua"] * 6 + ["limpieza"] * 6 + ["alumbrado"] * 6
CLASES = ["agua", "limpieza", "alumbrado"]


def test_comparar_algoritmos_devuelve_ganador_y_detalle() -> None:
    resultado = comparar_algoritmos(TEXTOS, ETIQUETAS)
    assert resultado["ganador"] in {
        "Naive Bayes Multinomial",
        "Regresión Logística",
        "LinearSVC (calibrado)",
    }
    assert len(resultado["detalle"]) >= 2
    for datos in resultado["detalle"].values():
        assert 0.0 <= datos["f1_macro"] <= 1.0


def test_construir_y_evaluar_clasificador() -> None:
    modelo, comparacion = construir_clasificador(TEXTOS, ETIQUETAS)
    metricas = evaluar(modelo, TEXTOS, ETIQUETAS, CLASES)

    assert comparacion["ganador"]
    assert metricas["accuracy"] <= 1.0 and metricas["accuracy"] > 0.0
    assert set(metricas["metricas_por_clase"].keys()) == set(CLASES)
    assert "matriz_confusion" in metricas
    assert "etiquetas_matriz" in metricas


def test_evaluar_por_validacion_cruzada() -> None:
    metricas = evaluar_por_validacion_cruzada(TEXTOS, ETIQUETAS, CLASES)
    assert metricas["metodo"] == "validacion_cruzada"
    assert 0.0 <= metricas["f1_macro"] <= 1.0


def test_curva_de_aprendizaje_crece_en_puntos() -> None:
    curva = curva_de_aprendizaje(TEXTOS, ETIQUETAS)
    assert len(curva["tamanos"]) == len(curva["f1_validacion"])
    assert all(t > 0 for t in curva["tamanos"])


def test_pares_confundidos_devuelve_solo_fuera_de_diagonal() -> None:
    matriz = [[2, 1, 0], [0, 3, 0], [0, 0, 4]]
    pares = pares_confundidos(matriz, CLASES)
    assert pares == [{"real": "agua", "predicha": "limpieza", "casos": 1}]


def test_una_sola_clase_no_rompe_el_entrenamiento() -> None:
    textos = ["solo un tema repetido"] * 5
    etiquetas = ["unica"] * 5
    modelo, comparacion = construir_clasificador(textos, etiquetas)
    assert modelo.predict(["solo un tema repetido"])[0] == "unica"
    assert comparacion["ganador"]
