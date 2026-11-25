# Informe del agente · Kiosco Ciudadano (Equipo # 3)

Documento generado automáticamente desde la base de datos y el modelo activo. Todas las cifras son reales y reproducibles (no hay valores simulados).

## 1. Cabecera

- **Fecha de generación:** 2026-11-24T18:25:01
- **Versión del modelo activa:** v8
- **Método de evaluación:** conjunto_prueba_fijo
- **Conjunto de prueba vigente:** prueba-g3
- **Ejemplos de entrenamiento:** 864
- **Ejemplos de prueba fija:** 116
- **Ejemplos de prueba externa:** 40
- **Etiquetas del pool de entrenamiento:** 980
- **Hash corto de los datos (SHA-256, 12 hex):** `156df645803a`
- **Umbrales de revisión (Ec. 9):** confianza ≥ 60% y margen ≥ 15%

## 2. Calidad del dataset

- **Etiquetas analizadas:** 980
- **Vocabulario único:** 1392 términos

### 2.1 Distribución por categoría

| Categoría | Nº ejemplos | % del total |
| --- | --- | --- |
| calles | 298 | 30.4% |
| alumbrado | 98 | 10.0% |
| limpieza | 98 | 10.0% |
| agua | 98 | 10.0% |
| seguridad | 97 | 9.9% |
| areas_verdes | 97 | 9.9% |
| drenaje | 97 | 9.9% |
| contaminacion | 97 | 9.9% |

> Desbalance: razón máx/mín = **3.07**, coeficiente de variación = **0.541**.

### 2.2 Distribución por prioridad

| Prioridad | Nº ejemplos | % del total |
| --- | --- | --- |
| ALTA | 428 | 43.7% |
| MEDIA | 382 | 39.0% |
| BAJA | 170 | 17.3% |

### 2.3 Longitud de los textos (palabras)

- Mínima: **5**, mediana: **19.0**, media: **19.9**, máxima: **39**.

### 2.4 Duplicados, casi-duplicados y contradicciones

- Duplicados exactos: **0** grupos (0 extra).
- Casi-duplicados (coseno TF-IDF ≥ 0.85): **10** extra en **10** grupos.
- Etiquetas contradictorias (mismo texto, categoría distinta): **0**.

## 3. Parámetros del modelo y comparación de algoritmos

### 3.1 Configuración del vectorizador TF-IDF

| Parámetro | Valor |
| --- | --- |
| Nº de características TF-IDF | 1377 |
| Tamaño del vocabulario | 1377 |
| ngram_range | [1, 1] |
| min_df | 1 |
| sublinear_tf | True |
| Nº de características (prioridad) | 5095 |

### 3.2 Clasificadores e hiperparámetros por clase

| Clase | Algoritmo | C | alpha | class_weight | max_iter | calibrado |
| --- | --- | --- | --- | --- | --- | --- |
| Categoría | LinearSVC (calibrado) | 1.0 | None | balanced | 1000 | True |
| Prioridad | Naive Bayes Multinomial | None | 0.1 | None | None | False |

### 3.3 División de datos y semilla

| Aspecto | Valor |
| --- | --- |
| Esquema | entrenamiento + conjunto de prueba fijo reservado por grupos de casi-duplicados (comparabilidad entre versiones) |
| Semilla | 42 |
| Entrenamiento | 864 |
| Prueba fija | 116 |
| Prueba externa | 40 |
| Folds máximos | 5 |
| Validación cruzada | StratifiedGroupKFold / StratifiedKFold agrupada por casi-duplicados |

### 3.4 Comparación de los 3 algoritmos (F1 macro de validación cruzada)

**Categoría** — ganador: `LinearSVC (calibrado)`

| Algoritmo | F1 macro | Accuracy | Precisión macro | Recall macro |
| --- | --- | --- | --- | --- |
| LinearSVC (calibrado) | 90.5% | 91.9% | 90.8% | 90.5% |
| Regresión Logística | 86.5% | 88.0% | 87.3% | 86.0% |
| Naive Bayes Multinomial | 58.6% | 60.8% | 91.9% | 48.9% |

**Prioridad** — ganador: `Naive Bayes Multinomial`

| Algoritmo | F1 macro | Accuracy | Precisión macro | Recall macro |
| --- | --- | --- | --- | --- |
| LinearSVC (calibrado) | 68.9% | 70.8% | 72.0% | 67.3% |
| Regresión Logística | 67.3% | 69.8% | 69.2% | 66.2% |
| Naive Bayes Multinomial | 54.0% | 66.3% | 75.1% | 55.6% |

> Leyenda de ecuaciones: TF-IDF en la vectorización (Ec. 1–3), puntaje lineal por clase (Ec. 4), objetivo de la SVM (Ec. 5), Naive Bayes como algoritmo comparado (Ec. 19) y softmax de la regresión logística (Ec. 20).

## 4. Métricas de categoría y prioridad (con IC de Wilson)

### 4.1 Categoría

| Conjunto | N | Accuracy (IC 95 %) | Precisión macro | Recall macro | F1 macro |
| --- | --- | --- | --- | --- | --- |
| Prueba fija | 116 | 98.3% [93.9%, 99.5%] | 98.4% | 98.3% | 98.3% |
| Prueba externa | 40 | 85.0% [70.9%, 92.9%] | 87.8% | 85.0% | 85.1% |

#### Categoría — métricas por clase (Ec. 10–12)

| Clase | Precisión | Recall | F1 | Soporte |
| --- | --- | --- | --- | --- |
| agua | 100.0% | 100.0% | 100.0% | 14 |
| calles | 93.8% | 100.0% | 96.8% | 15 |
| drenaje | 100.0% | 100.0% | 100.0% | 14 |
| limpieza | 100.0% | 100.0% | 100.0% | 15 |
| alumbrado | 100.0% | 93.3% | 96.5% | 15 |
| seguridad | 93.3% | 93.3% | 93.3% | 15 |
| areas_verdes | 100.0% | 100.0% | 100.0% | 14 |
| contaminacion | 100.0% | 100.0% | 100.0% | 14 |

#### Categoría — IC de Wilson por clase (Ec. 17)

| Clase | Precisión IC 95 % | Recall IC 95 % | Soporte |
| --- | --- | --- | --- |
| alumbrado | 100.0% [78.5%, 100.0%] | 93.3% [70.2%, 98.8%] | 15 |
| limpieza | 100.0% [79.6%, 100.0%] | 100.0% [79.6%, 100.0%] | 15 |
| calles | 93.8% [71.7%, 98.9%] | 100.0% [79.6%, 100.0%] | 15 |
| agua | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |
| seguridad | 93.3% [70.2%, 98.8%] | 93.3% [70.2%, 98.8%] | 15 |
| areas_verdes | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |
| drenaje | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |
| contaminacion | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |

### 4.2 Prioridad

| Conjunto | N | Accuracy (IC 95 %) | Precisión macro | Recall macro | F1 macro |
| --- | --- | --- | --- | --- | --- |
| Prueba fija | 116 | 94.0% [88.1%, 97.0%] | 95.3% | 93.9% | 94.6% |
| Prueba externa | 40 | 35.0% [22.1%, 50.5%] | — | — | 31.0% |

#### Prioridad — métricas por clase (Ec. 10–12)

| Clase | Precisión | Recall | F1 | Soporte |
| --- | --- | --- | --- | --- |
| ALTA | 93.1% | 94.7% | 93.9% | 57 |
| BAJA | 100.0% | 94.1% | 97.0% | 17 |
| MEDIA | 92.9% | 92.9% | 92.9% | 42 |

#### Prioridad — IC de Wilson por clase (Ec. 17)

| Clase | Precisión IC 95 % | Recall IC 95 % | Soporte |
| --- | --- | --- | --- |
| ALTA | 93.1% [83.6%, 97.3%] | 94.7% [85.6%, 98.2%] | 57 |
| MEDIA | 92.9% [81.0%, 97.5%] | 92.9% [81.0%, 97.5%] | 42 |
| BAJA | 100.0% [80.6%, 100.0%] | 94.1% [73.0%, 99.0%] | 17 |

## 5. Matrices de confusión (absolutas y normalizadas por fila)

### 5.1 Categoría (8×8)

**Absoluta (nº de casos)**

| real \ pred | alumbrad | limpieza | calles | agua | segurida | areas_ve | drenaje | contamin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alumbrado | 14 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| limpieza | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 |
| calles | 0 | 0 | 15 | 0 | 0 | 0 | 0 | 0 |
| agua | 0 | 0 | 0 | 14 | 0 | 0 | 0 | 0 |
| seguridad | 0 | 0 | 1 | 0 | 14 | 0 | 0 | 0 |
| areas_verdes | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 0 |
| drenaje | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 0 |
| contaminacion | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |

**Normalizada por fila (proporción)**

| real \ pred | alumbrad | limpieza | calles | agua | segurida | areas_ve | drenaje | contamin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alumbrado | 93.3% | 0.0% | 0.0% | 0.0% | 6.7% | 0.0% | 0.0% | 0.0% |
| limpieza | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| calles | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| agua | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| seguridad | 0.0% | 0.0% | 6.7% | 0.0% | 93.3% | 0.0% | 0.0% | 0.0% |
| areas_verdes | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| drenaje | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| contaminacion | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |

### 5.2 Prioridad (3×3)

**Absoluta (nº de casos)**

| real \ pred | ALTA | MEDIA | BAJA |
| --- | --- | --- | --- |
| ALTA | 54 | 3 | 0 |
| MEDIA | 3 | 39 | 0 |
| BAJA | 1 | 0 | 16 |

**Normalizada por fila (proporción)**

| real \ pred | ALTA | MEDIA | BAJA |
| --- | --- | --- | --- |
| ALTA | 94.7% | 5.3% | 0.0% |
| MEDIA | 7.1% | 92.9% | 0.0% |
| BAJA | 5.9% | 0.0% | 94.1% |

## 6. Baselines, calibración y curvas

### 6.1 Comparación con baselines

**Categoría**

| Clasificador | Accuracy | F1 macro |
| --- | --- | --- |
| Agente (modelo activo) | 98.3% | 98.3% |
| Clase mayoritaria (calles) | 12.9% | 2.9% |
| Aleatoria estratificada | 9.5% | 8.1% |

**Prioridad**

| Clasificador | Accuracy | F1 macro |
| --- | --- | --- |
| Agente (modelo activo) | 94.0% | 94.6% |
| Clase mayoritaria (ALTA) | 49.1% | 22.0% |
| Aleatoria estratificada | 37.1% | 31.4% |

### 6.2 Calibración de la confianza (Ec. 6, 15, 16)

| Rango de confianza | N | Confianza media | Exactitud real |
| --- | --- | --- | --- |
| [0.0%, 50.0%) | 2 | 39.5% | 100.0% |
| [50.0%, 60.0%) | 2 | 52.5% | 50.0% |
| [60.0%, 70.0%) | 7 | 67.2% | 85.7% |
| [70.0%, 80.0%) | 1 | 78.3% | 100.0% |
| [80.0%, 90.0%) | 15 | 85.6% | 100.0% |
| [90.0%, 100.0%) | 89 | 93.4% | 100.0% |

> Brier score: **0.0462** · ECE: **0.0930** · casos: **116**.

### 6.3 Curva cobertura-precisión y umbral de revisión (Ec. 9)

| Umbral de confianza | Cobertura | N aceptados | Precisión |
| --- | --- | --- | --- |
| 0% | 100.0% | 116 | 98.3% |
| 40% | 99.1% | 115 | 98.3% |
| 50% | 98.3% | 114 | 98.2% |
| 60% | 96.5% | 112 | 99.1% |
| 70% | 90.5% | 105 | 100.0% |
| 80% | 89.7% | 104 | 100.0% |
| 90% | 76.7% | 89 | 100.0% |
| 95% | 12.9% | 15 | 100.0% |

### 6.4 Análisis de errores

| Texto (recortado) | Real | Predicha | Confianza |
| --- | --- | --- | --- |
| `Necesitamos un botón de auxilio en la parada de transporte` | seguridad | calles | 69.3% |
| `Falta iluminación en la cancha del barrio y los jóvenes jueg` | alumbrado | seguridad | 51.0% |

### 6.5 Curva de aprendizaje

| Nº ejemplos | F1 entrenamiento | F1 validación |
| --- | --- | --- |
| 138 | 100.0% | 64.4% |
| 276 | 100.0% | 74.7% |
| 414 | 100.0% | 74.6% |
| 552 | 100.0% | 92.0% |
| 691 | 100.0% | 93.8% |

## 7. Eficiencia medida y evolución por versión

### 7.1 Eficiencia del modelo activo

| Métrica | Valor |
| --- | --- |
| Tiempo de entrenamiento | 11.184 s |
| Tamaño del modelo serializado | 843.93 KB |
| Nº de predicciones medidas | 500 |
| Textos distintos usados | 116 |
| Latencia media | 7.296 ms |
| Latencia p95 | 8.723 ms |

### 7.2 Evolución por versión válida (sin fuga de datos)

| Versión | Algoritmo | Entren. (s) | Modelo (KB) | Latencia p95 (ms) | Prueba | Accuracy cat. | F1 cat. | F1 prioridad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v5 | LinearSVC (calibrado) | — | — | — | 116 | 95.7% | 95.7% | 93.1% |
| v6 | LinearSVC (calibrado) | 193.280 | 292.87 | 428.267 | 116 | 95.7% | 95.7% | 93.1% |
| v7 | Regresión Logística | 113.051 | 186.44 | 29.706 | 116 | 97.4% | 97.5% | 93.8% |
| v8 (activa) | LinearSVC (calibrado) | 11.184 | 843.93 | 8.723 | 116 | 98.3% | 98.3% | 94.6% |

### 7.3 Versiones excluidas de la comparación (fuga de datos)

| Versión | Ejemplos (histórico) | Motivo de exclusión |
| --- | --- | --- |
| v1 | 64 | sin ids de entrenamiento registrados (versión anterior a la corrección) |
| v2 | 564 | sin ids de entrenamiento registrados (versión anterior a la corrección) |
| v3 | 564 | sin ids de entrenamiento registrados (versión anterior a la corrección) |
| v4 | 464 | sin ids de entrenamiento registrados (versión anterior a la corrección) |

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
| `tuberia` | 1 | 5.1978 | 0.50327 |
| `fuga` | 1 | 5.0547 | 0.48941 |
| `agua` | 2 | 2.9752 | 0.48775 |
| `potable` | 1 | 4.2074 | 0.40737 |
| `esquina` | 1 | 3.3201 | 0.32146 |

**Matriz documento-término TF-IDF reducida (8 términos más relevantes)**

| Documento \ término | `tuberia` | `fuga` | `agua` | `potable` | `esquina` |
| --- | --- | --- | --- | --- | --- |
| peso tf-idf | 0.50327 | 0.48941 | 0.48775 | 0.40737 | 0.32146 |

**7. Puntajes de decisión por clase (Ec. 4)**

| Clase | s_c(x) |
| --- | --- |
| `agua` | 2.74177 |
| `drenaje` | 0.04030 |
| `limpieza` | -0.22419 |
| `areas_verdes` | -0.34944 |
| `alumbrado` | -0.41935 |
| `seguridad` | -0.59379 |
| `contaminacion` | -0.65850 |
| `calles` | -0.81903 |

**8. Probabilidades calibradas de categoría (Ec. 6, 7)**

| Clase | Probabilidad |
| --- | --- |
| `agua` | 96.9% |
| `drenaje` | 2.2% |
| `limpieza` | 0.4% |
| `areas_verdes` | 0.2% |
| `alumbrado` | 0.1% |
| `seguridad` | 0.1% |
| `calles` | 0.1% |
| `contaminacion` | 0.1% |

**9–10. Margen y decisión (Ec. 8, 9)**

| Concepto | Valor |
| --- | --- |
| Confianza (categoría) | 96.85% |
| Umbral de confianza | 60% |
| ¿Cumple confianza? | True |
| Margen p₁ − p₂ | 94.70% |
| Umbral de margen | 15% |
| ¿Cumple margen? | True |
| Categoría final | `agua` |
| Prioridad final | `ALTA` |
| **Decisión final** | **automática** |

**11. Resumen equivalente para la PRIORIDAD**

| Clase | Puntaje s_c(x) | Probabilidad |
| --- | --- | --- |
| `ALTA` | -17.30894 | 76.5% |
| `MEDIA` | -18.41834 | 23.1% |
| `BAJA` | -21.67713 | 0.4% |

> Prioridad con mayor probabilidad: **`ALTA`** (confianza 76.49%, margen 53.37%).

### 8.2 Ejemplo 2 — origen: `prueba_fija_dudosa`

- **1. Texto original:** `Alerta vecinal: hay un criadero clandestino de animales en el pasaje Los Pinos que genera olores fuertes y plagas, ya lleva varios días así.`
- **2. Texto normalizado:** `alerta vecinal hay un criadero clandestino de animales en el pasaje los pinos que genera olores fuertes y plagas ya lleva varios dias asi`
- **3. Tokens (24):** `alerta`, `vecinal`, `hay`, `un`, `criadero`, `clandestino`, `de`, `animales`, `en`, `el`, `pasaje`, `los`, `pinos`, `que`, `genera`, `olores`, `fuertes`, `y`, `plagas`, `ya`, `lleva`, `varios`, `dias`, `asi`
- **4. Tokens sin stopwords (14):** `alerta`, `vecinal`, `criadero`, `clandestino`, `animales`, `pasaje`, `pinos`, `genera`, `olores`, `fuertes`, `plagas`, `lleva`, `varios`, `dias`
- **Stopwords eliminadas:** `asi`, `de`, `el`, `en`, `hay`, `los`, `que`, `un`, `ya`
- **5. N-gramas generados (14):** `alerta`, `vecinal`, `criadero`, `clandestino`, `animales`, `pasaje`, `pinos`, `genera`, `olores`, `fuertes`, `plagas`, `lleva`, `varios`, `dias`

**6. Términos con mayor peso TF-IDF (Ec. 1–3)**

| Término | tf | idf | tf-idf |
| --- | --- | --- | --- |
| `olores` | 1 | 7.0696 | 0.37703 |
| `animales` | 1 | 7.0696 | 0.37703 |
| `plagas` | 1 | 6.6641 | 0.35541 |
| `clandestino` | 1 | 5.9710 | 0.31844 |
| `fuertes` | 1 | 5.4601 | 0.29120 |
| `genera` | 1 | 5.2778 | 0.28147 |
| `pinos` | 1 | 4.5046 | 0.24024 |
| `alerta` | 1 | 4.3287 | 0.23086 |
| `pasaje` | 1 | 4.2970 | 0.22917 |
| `lleva` | 1 | 4.1518 | 0.22142 |

**Matriz documento-término TF-IDF reducida (8 términos más relevantes)**

| Documento \ término | `olores` | `animales` | `plagas` | `clandestino` | `fuertes` | `genera` | `pinos` | `alerta` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| peso tf-idf | 0.37703 | 0.37703 | 0.35541 | 0.31844 | 0.29120 | 0.28147 | 0.24024 | 0.23086 |

**7. Puntajes de decisión por clase (Ec. 4)**

| Clase | s_c(x) |
| --- | --- |
| `contaminacion` | 0.25283 |
| `limpieza` | 0.22051 |
| `areas_verdes` | 0.18062 |
| `seguridad` | 0.08553 |
| `alumbrado` | 0.00120 |
| `drenaje` | -0.01311 |
| `agua` | -0.02019 |
| `calles` | -0.62255 |

**8. Probabilidades calibradas de categoría (Ec. 6, 7)**

| Clase | Probabilidad |
| --- | --- |
| `contaminacion` | 34.9% |
| `seguridad` | 21.3% |
| `areas_verdes` | 15.7% |
| `limpieza` | 15.0% |
| `alumbrado` | 4.2% |
| `drenaje` | 3.5% |
| `agua` | 3.3% |
| `calles` | 2.1% |

**9–10. Margen y decisión (Ec. 8, 9)**

| Concepto | Valor |
| --- | --- |
| Confianza (categoría) | 34.86% |
| Umbral de confianza | 60% |
| ¿Cumple confianza? | False |
| Margen p₁ − p₂ | 13.52% |
| Umbral de margen | 15% |
| ¿Cumple margen? | False |
| Categoría final | `contaminacion` |
| Prioridad final | `ALTA` |
| **Decisión final** | **revisión humana** |

**11. Resumen equivalente para la PRIORIDAD**

| Clase | Puntaje s_c(x) | Probabilidad |
| --- | --- | --- |
| `MEDIA` | -30.28296 | 47.7% |
| `ALTA` | -30.34823 | 48.8% |
| `BAJA` | -32.10371 | 3.5% |

> Prioridad con mayor probabilidad: **`ALTA`** (confianza 48.79%, margen 1.06%).

## 9. Librerías y versiones instaladas

> Versiones leídas realmente del entorno con `importlib.metadata` (ninguna escrita a mano).

| Librería | Versión instalada |
| --- | --- |
| scikit-learn | 1.7.2 |
| numpy | 2.2.6 |
| scipy | 1.15.3 |
| pandas | 2.3.3 |
| joblib | 1.6.0 |
| fastapi | 0.162.5 |
| starlette | 1.7.0 |
| pydantic | 2.14.4 |
| uvicorn | 0.54.0 |
| sqlalchemy | 2.0.58 |
| alembic | 1.20.1 |
| psycopg2-binary | 2.9.13 |
| python-dotenv | 1.2.4 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |

> El agente usa `scikit-learn` (TfidfVectorizer, MultinomialNB, LogisticRegression, LinearSVC, CalibratedClassifierCV, DummyClassifier, StratifiedKFold, StratifiedGroupKFold, learning_curve, metrics) sobre `FastAPI` + `SQLAlchemy` + `PostgreSQL` (Supabase).
