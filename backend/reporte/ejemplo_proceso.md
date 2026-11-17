# Ejemplo de proceso del agente

- **Versión del modelo:** v5
- **Hash de los datos:** `76ea27372094`
- **Fecha:** 2026-11-16T18:52:56

## 8. Ejemplo de proceso del agente (las 11 etapas)

Diagrama del pipeline: **texto → normalización → tokens/stopwords → n-gramas → TF-IDF → clasificador → calibración → decisión por umbral/margen → resultado o revisión humana**.

### 8.1 Ejemplo 1 — origen: `prueba_fija_alta_confianza`

- **1. Texto original:** `Hay una fuga de agua potable en la tubería de la esquina y se pierde mucha agua`
- **2. Texto normalizado:** `hay una fuga de agua potable en la tuberia de la esquina y se pierde mucha agua`
- **3. Tokens (17):** `hay`, `una`, `fuga`, `de`, `agua`, `potable`, `en`, `la`, `tuberia`, `de`, `la`, `esquina`, `y`, `se`, `pierde`, `mucha`, `agua`
- **4. Tokens sin stopwords (7):** `fuga`, `agua`, `potable`, `tuberia`, `esquina`, `pierde`, `agua`
- **Stopwords eliminadas:** `de`, `en`, `hay`, `la`, `mucha`, `se`, `una`
- **5. N-gramas generados (7):** `fuga`, `agua`, `potable`, `tuberia`, `esquina`, `pierde`, `agua`

**6. Términos con mayor peso TF-IDF (Ec. 1–3)**

| Término | tf | idf | tf-idf |
| --- | --- | --- | --- |
| `tuberia` | 1 | 5.5326 | 0.55784 |
| `fuga` | 1 | 4.8395 | 0.48795 |
| `agua` | 2 | 2.6877 | 0.45883 |
| `potable` | 1 | 3.8839 | 0.39161 |
| `esquina` | 1 | 2.9225 | 0.29467 |

**Matriz documento-término TF-IDF reducida (8 términos más relevantes)**

| Documento \ término | `tuberia` | `fuga` | `agua` | `potable` | `esquina` |
| --- | --- | --- | --- | --- | --- |
| peso tf-idf | 0.55784 | 0.48795 | 0.45883 | 0.39161 | 0.29467 |

**7. Puntajes de decisión por clase (Ec. 4)**

| Clase | s_c(x) |
| --- | --- |
| `agua` | 2.61188 |
| `drenaje` | -0.03810 |
| `areas_verdes` | -0.27469 |
| `limpieza` | -0.38099 |
| `alumbrado` | -0.42068 |
| `contaminacion` | -0.50436 |
| `calles` | -0.58696 |
| `seguridad` | -0.67447 |

**8. Probabilidades calibradas de categoría (Ec. 6, 7)**

| Clase | Probabilidad |
| --- | --- |
| `agua` | 93.6% |
| `drenaje` | 2.1% |
| `areas_verdes` | 1.3% |
| `limpieza` | 0.8% |
| `calles` | 0.7% |
| `alumbrado` | 0.6% |
| `contaminacion` | 0.6% |
| `seguridad` | 0.4% |

**9–10. Margen y decisión (Ec. 8, 9)**

| Concepto | Valor |
| --- | --- |
| Confianza (categoría) | 93.62% |
| Umbral de confianza | 60% |
| ¿Cumple confianza? | True |
| Margen p₁ − p₂ | 91.55% |
| Umbral de margen | 15% |
| ¿Cumple margen? | True |
| Categoría final | `agua` |
| Prioridad final | `ALTA` |
| **Decisión final** | **automática** |

**11. Resumen equivalente para la PRIORIDAD**

| Clase | Puntaje s_c(x) | Probabilidad |
| --- | --- | --- |
| `ALTA` | -12.33097 | 69.3% |
| `MEDIA` | -13.19262 | 28.7% |
| `BAJA` | -15.08253 | 2.0% |

> Prioridad con mayor probabilidad: **`ALTA`** (confianza 69.33%, margen 40.65%).

### 8.2 Ejemplo 2 — origen: `prueba_fija_dudosa`

- **1. Texto original:** `Necesitamos un botón de auxilio en la parada de transporte`
- **2. Texto normalizado:** `necesitamos un boton de auxilio en la parada de transporte`
- **3. Tokens (10):** `necesitamos`, `un`, `boton`, `de`, `auxilio`, `en`, `la`, `parada`, `de`, `transporte`
- **4. Tokens sin stopwords (5):** `necesitamos`, `boton`, `auxilio`, `parada`, `transporte`
- **Stopwords eliminadas:** `de`, `en`, `la`, `un`
- **5. N-gramas generados (5):** `necesitamos`, `boton`, `auxilio`, `parada`, `transporte`

**6. Términos con mayor peso TF-IDF (Ec. 1–3)**

| Término | tf | idf | tf-idf |
| --- | --- | --- | --- |
| `parada` | 1 | 4.2517 | 0.80811 |
| `necesitamos` | 1 | 3.0990 | 0.58902 |

**Matriz documento-término TF-IDF reducida (8 términos más relevantes)**

| Documento \ término | `parada` | `necesitamos` |
| --- | --- | --- |
| peso tf-idf | 0.80811 | 0.58902 |

**7. Puntajes de decisión por clase (Ec. 4)**

| Clase | s_c(x) |
| --- | --- |
| `limpieza` | 0.14529 |
| `areas_verdes` | 0.14102 |
| `seguridad` | 0.11064 |
| `calles` | -0.02713 |
| `agua` | -0.04463 |
| `drenaje` | -0.11671 |
| `alumbrado` | -0.12077 |
| `contaminacion` | -0.21343 |

**8. Probabilidades calibradas de categoría (Ec. 6, 7)**

| Clase | Probabilidad |
| --- | --- |
| `seguridad` | 25.8% |
| `calles` | 18.1% |
| `areas_verdes` | 17.3% |
| `limpieza` | 17.1% |
| `alumbrado` | 6.2% |
| `agua` | 5.7% |
| `contaminacion` | 5.6% |
| `drenaje` | 4.2% |

**9–10. Margen y decisión (Ec. 8, 9)**

| Concepto | Valor |
| --- | --- |
| Confianza (categoría) | 25.81% |
| Umbral de confianza | 60% |
| ¿Cumple confianza? | False |
| Margen p₁ − p₂ | 7.68% |
| Umbral de margen | 15% |
| ¿Cumple margen? | False |
| Categoría final | `seguridad` |
| Prioridad final | `ALTA` |
| **Decisión final** | **revisión humana** |

**11. Resumen equivalente para la PRIORIDAD**

| Clase | Puntaje s_c(x) | Probabilidad |
| --- | --- | --- |
| `BAJA` | -7.51680 | 27.3% |
| `ALTA` | -7.85531 | 43.2% |
| `MEDIA` | -8.21866 | 29.4% |

> Prioridad con mayor probabilidad: **`ALTA`** (confianza 43.24%, margen 13.80%).
