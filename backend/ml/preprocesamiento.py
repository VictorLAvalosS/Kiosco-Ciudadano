"""Preprocesamiento de texto en español para el clasificador de solicitudes.

Pasos:
  1. Convertir a minúsculas.
  2. Quitar acentos (normalización NFD + eliminación de diacríticos).
  3. Eliminar signos de puntuación.
  4. Eliminar stopwords del español.
"""

from __future__ import annotations

import re
import unicodedata

# Stopwords del español usadas por el pipeline. Se almacenan ya normalizadas
# (sin tildes) para comparar contra el texto normalizado.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "al", "algo", "algunas", "algunos", "ante", "antes", "aquel", "aquella",
        "aquellas", "aquellos", "aqui", "asi", "aun", "bajo", "bastante", "cada", "casi",
        "cierta", "ciertas", "cierto", "ciertos", "como", "con", "conmigo", "contigo",
        "contra", "cual", "cuales", "cuando", "cuanto", "cuanta", "de", "del", "demas",
        "desde", "donde", "dos", "el", "ella", "ellas", "ello", "ellos", "en", "entre",
        "era", "eran", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estan", "estar",
        "estas", "este", "esto", "estos", "fue", "ha", "haber", "hace", "hacia", "han",
        "hasta", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me", "menos", "mi",
        "mis", "mucho", "mucha", "muchos", "muchas", "muy", "nada", "ni", "no", "nos",
        "nosotras", "nosotros", "nuestra", "nuestro", "nuestras", "nuestros", "o", "os",
        "otra", "otras", "otro", "otros", "para", "pero", "poco", "por", "porque", "que",
        "quien", "quienes", "se", "sea", "segun", "ser", "si", "sin", "sobre", "sois",
        "somos", "son", "soy", "su", "sus", "tal", "tambien", "tanta", "tantas", "tanto",
        "tantos", "te", "tenemos", "tener", "tengo", "ti", "tiene", "tienen", "todo",
        "toda", "todos", "todas", "tu", "tus", "un", "una", "uno", "unos", "unas",
        "usted", "ustedes", "ya", "yo", "seria", "sido", "parte", "cerca", "favor", "urge",
    }
)

# Expresión para conservar solo letras sin tildes, números y espacios.
# Se aplica después de `quitar_acentos`, por lo que el rango a-z es suficiente.
_NO_ALFANUMERICO = re.compile(r"[^0-9a-z\s]", re.UNICODE)


def quitar_acentos(texto: str) -> str:
    """Elimina los diacríticos (tildes, diéresis) de un texto."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(caracter for caracter in descompuesto if not unicodedata.combining(caracter))


def normalizar(texto: str) -> str:
    """Normaliza el texto: minúsculas, sin tildes, sin signos y sin espacios dobles."""
    texto = texto.lower()
    texto = quitar_acentos(texto)
    texto = _NO_ALFANUMERICO.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto: str) -> list[str]:
    """Devuelve los tokens normalizados, sin stopwords ni tokens de una sola letra."""
    tokens = normalizar(texto).split()
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def texto_limpio(texto: str) -> str:
    """Texto normalizado con stopwords eliminadas; es la entrada del vectorizador."""
    return " ".join(tokenizar(texto))
