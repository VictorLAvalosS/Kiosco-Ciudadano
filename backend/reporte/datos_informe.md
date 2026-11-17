# Informe del agente · Kiosco Ciudadano (Equipo # 3)

Documento generado automáticamente desde la base de datos y el modelo activo. Todas las cifras son reales y reproducibles (no hay valores simulados).

## 1. Cabecera

- **Fecha de generación:** 2026-11-16T18:59:30
- **Versión del modelo activa:** v6
- **Método de evaluación:** conjunto_prueba_fijo
- **Conjunto de prueba vigente:** prueba-g3
- **Ejemplos de entrenamiento:** 464
- **Ejemplos de prueba fija:** 116
- **Ejemplos de prueba externa:** 40
- **Etiquetas del pool de entrenamiento:** 580
- **Hash corto de los datos (SHA-256, 12 hex):** `76ea27372094`
- **Umbrales de revisión (Ec. 9):** confianza ≥ 60% y margen ≥ 15%

## 2. Calidad del dataset

- **Etiquetas analizadas:** 580
- **Vocabulario único:** 726 términos

### 2.1 Distribución por categoría

| Categoría | Nº ejemplos | % del total |
| --- | --- | --- |
| alumbrado | 73 | 12.6% |
| limpieza | 73 | 12.6% |
| calles | 73 | 12.6% |
| agua | 73 | 12.6% |
| seguridad | 72 | 12.4% |
| areas_verdes | 72 | 12.4% |
| drenaje | 72 | 12.4% |
| contaminacion | 72 | 12.4% |

> Desbalance: razón máx/mín = **1.01**, coeficiente de variación = **0.007**.

### 2.2 Distribución por prioridad

| Prioridad | Nº ejemplos | % del total |
| --- | --- | --- |
| ALTA | 248 | 42.8% |
| MEDIA | 229 | 39.5% |
| BAJA | 103 | 17.8% |

### 2.3 Longitud de los textos (palabras)

- Mínima: **8**, mediana: **28.0**, media: **26.4**, máxima: **39**.

### 2.4 Duplicados, casi-duplicados y contradicciones

- Duplicados exactos: **0** grupos (0 extra).
- Casi-duplicados (coseno TF-IDF ≥ 0.85): **11** extra en **11** grupos.
- Etiquetas contradictorias (mismo texto, categoría distinta): **0**.

## 3. Parámetros del modelo y comparación de algoritmos

### 3.1 Configuración del vectorizador TF-IDF

| Parámetro | Valor |
| --- | --- |
| Nº de características TF-IDF | 697 |
| Tamaño del vocabulario | 697 |
| ngram_range | [1, 1] |
| min_df | 1 |
| sublinear_tf | True |
| Nº de características (prioridad) | 697 |

### 3.2 Clasificadores e hiperparámetros por clase

| Clase | Algoritmo | C | alpha | class_weight | max_iter | calibrado |
| --- | --- | --- | --- | --- | --- | --- |
| Categoría | LinearSVC (calibrado) | 5.0 | None | balanced | 1000 | True |
| Prioridad | Naive Bayes Multinomial | None | 0.1 | None | None | False |

### 3.3 División de datos y semilla

| Aspecto | Valor |
| --- | --- |
| Esquema | entrenamiento + conjunto de prueba fijo reservado por grupos de casi-duplicados (comparabilidad entre versiones) |
| Semilla | 42 |
| Entrenamiento | 464 |
| Prueba fija | 116 |
| Prueba externa | 40 |
| Folds máximos | 5 |
| Validación cruzada | StratifiedGroupKFold / StratifiedKFold agrupada por casi-duplicados |

### 3.4 Comparación de los 3 algoritmos (F1 macro de validación cruzada)

**Categoría** — ganador: `LinearSVC (calibrado)`

| Algoritmo | F1 macro | Accuracy | Precisión macro | Recall macro |
| --- | --- | --- | --- | --- |
| LinearSVC (calibrado) | 89.9% | 89.9% | 90.0% | 89.8% |
| Regresión Logística | 88.5% | 88.6% | 88.7% | 88.5% |
| Naive Bayes Multinomial | 85.8% | 85.8% | 86.2% | 85.8% |

**Prioridad** — ganador: `Naive Bayes Multinomial`

| Algoritmo | F1 macro | Accuracy | Precisión macro | Recall macro |
| --- | --- | --- | --- | --- |
| LinearSVC (calibrado) | 80.5% | 80.8% | 82.5% | 79.2% |
| Regresión Logística | 79.4% | 80.2% | 80.4% | 78.7% |
| Naive Bayes Multinomial | 67.3% | 73.9% | 81.8% | 66.0% |

> Leyenda de ecuaciones: TF-IDF en la vectorización (Ec. 1–3), puntaje lineal por clase (Ec. 4), objetivo de la SVM (Ec. 5), Naive Bayes como algoritmo comparado (Ec. 19) y softmax de la regresión logística (Ec. 20).

## 4. Métricas de categoría y prioridad (con IC de Wilson)

### 4.1 Categoría

| Conjunto | N | Accuracy (IC 95 %) | Precisión macro | Recall macro | F1 macro |
| --- | --- | --- | --- | --- | --- |
| Prueba fija | 116 | 95.7% [90.3%, 98.2%] | 95.8% | 95.7% | 95.7% |
| Prueba externa | 40 | 85.0% [70.9%, 92.9%] | 86.9% | 85.0% | 84.8% |

#### Categoría — métricas por clase (Ec. 10–12)

| Clase | Precisión | Recall | F1 | Soporte |
| --- | --- | --- | --- | --- |
| agua | 100.0% | 100.0% | 100.0% | 14 |
| calles | 93.3% | 93.3% | 93.3% | 15 |
| drenaje | 100.0% | 100.0% | 100.0% | 14 |
| limpieza | 100.0% | 100.0% | 100.0% | 15 |
| alumbrado | 100.0% | 100.0% | 100.0% | 15 |
| seguridad | 87.5% | 93.3% | 90.3% | 15 |
| areas_verdes | 92.9% | 92.9% | 92.9% | 14 |
| contaminacion | 92.3% | 85.7% | 88.9% | 14 |

#### Categoría — IC de Wilson por clase (Ec. 17)

| Clase | Precisión IC 95 % | Recall IC 95 % | Soporte |
| --- | --- | --- | --- |
| alumbrado | 100.0% [79.6%, 100.0%] | 100.0% [79.6%, 100.0%] | 15 |
| limpieza | 100.0% [79.6%, 100.0%] | 100.0% [79.6%, 100.0%] | 15 |
| calles | 93.3% [70.2%, 98.8%] | 93.3% [70.2%, 98.8%] | 15 |
| agua | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |
| seguridad | 87.5% [64.0%, 96.5%] | 93.3% [70.2%, 98.8%] | 15 |
| areas_verdes | 92.9% [68.5%, 98.7%] | 92.9% [68.5%, 98.7%] | 14 |
| drenaje | 100.0% [78.5%, 100.0%] | 100.0% [78.5%, 100.0%] | 14 |
| contaminacion | 92.3% [66.7%, 98.6%] | 85.7% [60.1%, 96.0%] | 14 |

### 4.2 Prioridad

| Conjunto | N | Accuracy (IC 95 %) | Precisión macro | Recall macro | F1 macro |
| --- | --- | --- | --- | --- | --- |
| Prueba fija | 116 | 93.1% [87.0%, 96.5%] | 94.6% | 91.9% | 93.1% |
| Prueba externa | 40 | 45.0% [30.7%, 60.2%] | — | — | 43.0% |

#### Prioridad — métricas por clase (Ec. 10–12)

| Clase | Precisión | Recall | F1 | Soporte |
| --- | --- | --- | --- | --- |
| ALTA | 93.1% | 94.7% | 93.9% | 57 |
| BAJA | 100.0% | 88.2% | 93.8% | 17 |
| MEDIA | 90.7% | 92.9% | 91.8% | 42 |

#### Prioridad — IC de Wilson por clase (Ec. 17)

| Clase | Precisión IC 95 % | Recall IC 95 % | Soporte |
| --- | --- | --- | --- |
| ALTA | 93.1% [83.6%, 97.3%] | 94.7% [85.6%, 98.2%] | 57 |
| MEDIA | 90.7% [78.4%, 96.3%] | 92.9% [81.0%, 97.5%] | 42 |
| BAJA | 100.0% [79.6%, 100.0%] | 88.2% [65.7%, 96.7%] | 17 |

## 5. Matrices de confusión (absolutas y normalizadas por fila)

### 5.1 Categoría (8×8)

**Absoluta (nº de casos)**

| real \ pred | alumbrad | limpieza | calles | agua | segurida | areas_ve | drenaje | contamin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alumbrado | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| limpieza | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 |
| calles | 0 | 0 | 14 | 0 | 0 | 1 | 0 | 0 |
| agua | 0 | 0 | 0 | 14 | 0 | 0 | 0 | 0 |
| seguridad | 0 | 0 | 0 | 0 | 14 | 0 | 0 | 1 |
| areas_verdes | 0 | 0 | 1 | 0 | 0 | 13 | 0 | 0 |
| drenaje | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 0 |
| contaminacion | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 12 |

**Normalizada por fila (proporción)**

| real \ pred | alumbrad | limpieza | calles | agua | segurida | areas_ve | drenaje | contamin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alumbrado | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| limpieza | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| calles | 0.0% | 0.0% | 93.3% | 0.0% | 0.0% | 6.7% | 0.0% | 0.0% |
| agua | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| seguridad | 0.0% | 0.0% | 0.0% | 0.0% | 93.3% | 0.0% | 0.0% | 6.7% |
| areas_verdes | 0.0% | 0.0% | 7.1% | 0.0% | 0.0% | 92.9% | 0.0% | 0.0% |
| drenaje | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% |
| contaminacion | 0.0% | 0.0% | 0.0% | 0.0% | 14.3% | 0.0% | 0.0% | 85.7% |

### 5.2 Prioridad (3×3)

**Absoluta (nº de casos)**

| real \ pred | ALTA | MEDIA | BAJA |
| --- | --- | --- | --- |
| ALTA | 54 | 3 | 0 |
| MEDIA | 3 | 39 | 0 |
| BAJA | 1 | 1 | 15 |

**Normalizada por fila (proporción)**

| real \ pred | ALTA | MEDIA | BAJA |
| --- | --- | --- | --- |
| ALTA | 94.7% | 5.3% | 0.0% |
| MEDIA | 7.1% | 92.9% | 0.0% |
| BAJA | 5.9% | 5.9% | 88.2% |

## 6. Baselines, calibración y curvas

### 6.1 Comparación con baselines

**Categoría**

| Clasificador | Accuracy | F1 macro |
| --- | --- | --- |
| Agente (modelo activo) | 95.7% | 95.7% |
| Clase mayoritaria (agua) | 12.1% | 2.7% |
| Aleatoria estratificada | 12.9% | 12.5% |

**Prioridad**

| Clasificador | Accuracy | F1 macro |
| --- | --- | --- |
| Agente (modelo activo) | 93.1% | 93.1% |
| Clase mayoritaria (ALTA) | 49.1% | 22.0% |
| Aleatoria estratificada | 37.1% | 31.4% |

### 6.2 Calibración de la confianza (Ec. 6, 15, 16)

| Rango de confianza | N | Confianza media | Exactitud real |
| --- | --- | --- | --- |
| [0.0%, 50.0%) | 6 | 39.8% | 16.7% |
| [50.0%, 60.0%) | 2 | 57.6% | 100.0% |
| [60.0%, 70.0%) | 0 | — | — |
| [70.0%, 80.0%) | 8 | 74.5% | 100.0% |
| [80.0%, 90.0%) | 60 | 88.3% | 100.0% |
| [90.0%, 100.0%) | 40 | 91.0% | 100.0% |

> Brier score: **0.0643** · ECE: **0.1288** · casos: **116**.

### 6.3 Curva cobertura-precisión y umbral de revisión (Ec. 9)

| Umbral de confianza | Cobertura | N aceptados | Precisión |
| --- | --- | --- | --- |
| 0% | 100.0% | 116 | 95.7% |
| 40% | 98.3% | 114 | 96.5% |
| 50% | 94.8% | 110 | 100.0% |
| 60% | 93.1% | 108 | 100.0% |
| 70% | 93.1% | 108 | 100.0% |
| 80% | 86.2% | 100 | 100.0% |
| 90% | 34.5% | 40 | 100.0% |
| 95% | 0.0% | 0 | — |

### 6.4 Análisis de errores

| Texto (recortado) | Real | Predicha | Confianza |
| --- | --- | --- | --- |
| `Se escuchan detonaciones de arma de fuego en la madrugada` | seguridad | contaminacion | 45.1% |
| `Pedimos pintar un paso peatonal frente al colegio` | calles | areas_verdes | 44.9% |
| `Las bancas del parque están rotas y no se pueden usar` | areas_verdes | calles | 43.2% |
| `Alerta vecinal: hay un criadero clandestino de animales en e` | contaminacion | seguridad | 41.8% |
| `Es urgente atender esto: hay un criadero clandestino de anim` | contaminacion | seguridad | 38.0% |

### 6.5 Curva de aprendizaje

| Nº ejemplos | F1 entrenamiento | F1 validación |
| --- | --- | --- |
| 74 | 100.0% | 44.3% |
| 148 | 100.0% | 73.7% |
| 222 | 100.0% | 86.7% |
| 296 | 100.0% | 90.6% |
| 371 | 100.0% | 92.7% |

## 7. Eficiencia medida y evolución por versión

### 7.1 Eficiencia del modelo activo

| Métrica | Valor |
| --- | --- |
| Tiempo de entrenamiento | 193.280 s |
| Tamaño del modelo serializado | 292.87 KB |
| Nº de predicciones medidas | 500 |
| Textos distintos usados | 116 |
| Latencia media | 111.864 ms |
| Latencia p95 | 428.267 ms |

### 7.2 Evolución por versión válida (sin fuga de datos)

| Versión | Algoritmo | Entren. (s) | Modelo (KB) | Latencia p95 (ms) | Prueba | Accuracy cat. | F1 cat. | F1 prioridad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v5 | LinearSVC (calibrado) | — | — | — | 116 | 95.7% | 95.7% | 93.1% |
| v6 (activa) | LinearSVC (calibrado) | 193.280 | 292.87 | 428.267 | 116 | 95.7% | 95.7% | 93.1% |

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
| `areas_verdes` | -0.27468 |
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
| `areas_verdes` | 0.14101 |
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

## 9. Librerías y versiones instaladas

> Versiones leídas realmente del entorno con `importlib.metadata` (ninguna escrita a mano).

| Librería | Versión instalada |
| --- | --- |
| scikit-learn | 1.9.1 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| pandas | 3.1.1 |
| joblib | 1.6.0 |
| fastapi | 0.163.0 |
| starlette | 1.10.0 |
| pydantic | 2.14.3 |
| uvicorn | 0.54.0 |
| sqlalchemy | 2.1.8 |
| alembic | 1.20.1 |
| psycopg2-binary | 2.9.13 |
| python-dotenv | 1.2.3 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |

> El agente usa `scikit-learn` (TfidfVectorizer, MultinomialNB, LogisticRegression, LinearSVC, CalibratedClassifierCV, DummyClassifier, StratifiedKFold, StratifiedGroupKFold, learning_curve, metrics) sobre `FastAPI` + `SQLAlchemy` + `PostgreSQL` (Supabase).
