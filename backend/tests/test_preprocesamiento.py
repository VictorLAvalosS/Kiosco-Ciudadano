"""Pruebas del módulo de preprocesamiento de texto."""

from __future__ import annotations

from ml.preprocesamiento import STOPWORDS, normalizar, quitar_acentos, texto_limpio, tokenizar


def test_quitar_acentos() -> None:
    assert quitar_acentos("Iluminación pública") == "Iluminacion publica"


def test_normalizar_minusculas_sin_tildes_sin_signos() -> None:
    resultado = normalizar("¡Fuga de AGUA en la esquina, urgente!")
    assert resultado == "fuga de agua en la esquina urgente"


def test_normalizar_colapsa_espacios() -> None:
    assert normalizar("mucho    espacio\n\tnueva linea") == "mucho espacio nueva linea"


def test_tokenizar_elimina_stopwords_y_palabras_cortas() -> None:
    tokens = tokenizar("el agua de la calle y un bache")
    assert "el" not in tokens
    assert "de" not in tokens
    assert "y" not in tokens
    assert "agua" in tokens
    assert "calle" in tokens
    assert "bache" in tokens


def test_tokenizar_descarta_tokens_de_una_letra() -> None:
    tokens = tokenizar("solo la a b c d palabras")
    assert all(len(token) > 1 for token in tokens)


def test_stopwords_estan_normalizadas() -> None:
    # Ninguna stopword debe contener tildes ni mayúsculas.
    for palabra in STOPWORDS:
        assert palabra == palabra.lower()
        assert "á" not in palabra and "é" not in palabra and "í" not in palabra


def test_texto_limpio_es_idempotente() -> None:
    una_vez = texto_limpio("Fuga de agua potable en la vía pública")
    dos_veces = texto_limpio(una_vez)
    assert una_vez == dos_veces
