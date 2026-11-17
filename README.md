# Kiosco Ciudadano · Panel Administrativo

Sistema inteligente para **clasificar solicitudes ciudadanas** de las Organizaciones
Territoriales de Base (OTB). Área: **Aprendizaje Supervisado** · Subárea:
**Procesamiento de Lenguaje Natural**.

El agente se entrena **realmente** con solicitudes etiquetadas por el equipo y
guardadas en **PostgreSQL (Supabase)**. Cada cifra que muestra la interfaz proviene
de la base de datos o de un entrenamiento real: **no hay valores inventados**.

## Arquitectura

```
React + Vite + TypeScript + Tailwind  ──fetch /api──▶  FastAPI (backend)
        (frontend, puerto 5173)            (proxy Vite)     │
                                                            ▼
                                            SQLAlchemy ORM + scikit-learn
                                                            │
                                                            ▼
                                              PostgreSQL (Supabase, RLS activo)
```

- El **frontend nunca se conecta a la base de datos**: consume la API por `fetch`
  (en desarrollo, el proxy de Vite reenvía `/api` a `http://127.0.0.1:8000`).
- El **backend es el único cliente** de la base de datos.
- Todas las credenciales se leen **solo** de variables de entorno.

## Categorías (8, fijas)

| # | Clave | Nombre | Criterio |
|---|-------|--------|----------|
| 1 | `alumbrado` | Alumbrado público | Postes, luminarias, cableado eléctrico |
| 2 | `limpieza` | Limpieza y residuos sólidos | Basura, contenedores, barrido |
| 3 | `calles` | Calles y vías públicas | Baches, aceras, señalización |
| 4 | `agua` | Agua potable y alcantarillado | Red de agua potable y aguas servidas/negras |
| 5 | `seguridad` | Seguridad ciudadana | Patrullaje, iluminación de riesgo, delitos |
| 6 | `areas_verdes` | Áreas verdes y espacios públicos | Parques, plazas, poda |
| 7 | `drenaje` | Drenaje y desagüe pluvial | Agua de lluvia, canales, cunetas, sumideros |
| 8 | `contaminacion` | Contaminación ambiental | Humo, vertidos, ruido, escombros |

**Prioridades:** `ALTA` (riesgo para personas o emergencia) · `MEDIA` (afecta el
servicio hace días) · `BAJA` (mejora o mantenimiento).

## Proceso del agente (traza de 11 etapas)

`POST /api/predecir` no devuelve solo la categoría: devuelve la **traza real** del
pipeline de inferencia, paso a paso, calculada con el **modelo activo** (la interfaz la
muestra en *Prueba del agente*). Cada etapa usa los valores reales del vectorizador y del
clasificador; no hay cifras fijas.

| # | Etapa | Clave de la traza | Qué muestra |
|---|-------|-------------------|-------------|
| 1 | Texto original | `texto_original` | El reclamo tal cual lo escribió la persona |
| 2 | Normalización | `texto_normalizado` | Minúsculas, sin tildes ni signos |
| 3 | Tokenización | `tokens` | Palabras ya normalizadas |
| 4 | Sin stopwords | `tokens_sin_stopwords` · `stopwords_eliminadas` | Tokens útiles y los descartados |
| 5 | N-gramas | `n_gramas` | Unigramas y bigramas del analizador TF-IDF |
| 6 | Peso TF-IDF (Ec.2–3) | `terminos_tfidf` | Términos con su `tf`, su `idf` real y el peso final |
| 7 | Puntaje por clase (Ec.4) | `puntajes_categoria` | s_c(x) = w_c·x + b_c para las 8 categorías |
| 8 | Probabilidades calibradas (Ec.6–7, 20) | `probabilidades_categoria` | Distribución de probabilidad que suma 1 |
| 9 | Margen de decisión (Ec.8) | `margen_categoria` | Diferencia entre la 1ª y la 2ª clase |
| 10 | Umbrales y decisión (Ec.9) | `decision` | Si confianza ≥ 60 % **y** margen ≥ 15 % ⇒ automática; si no ⇒ revisión humana |
| 11 | Prioridad | `prioridad` | El mismo resumen para `ALTA`/`MEDIA`/`BAJA` |

Los **parámetros** con los que se produjo esa traza se consultan en
`GET /api/modelo/parametros` (algoritmos, hiperparámetros, TF-IDF, división de datos,
umbrales y eficiencia medida) y la interfaz los muestra en *Modelo → Configuración y
parámetros del modelo activo*.

## Requisitos

- Node.js 20+ y npm
- Python 3.12+ (probado con 3.14)
- Una base de datos PostgreSQL en Supabase (o compatible)

## Puesta en marcha paso a paso

### 1. Base de datos y variables de entorno

Crea `backend/.env` (a partir de `backend/.env.example`) con la cadena del
**Session pooler** de Supabase. El `.env` está en `.gitignore` y **nunca** debe
subirse al repositorio.

```
DATABASE_URL=postgresql+psycopg2://postgres.<project-ref>:<clave>@aws-1-<region>.pooler.supabase.com:5432/postgres
CORS_ORIGINS=http://localhost:5173
ETIQUETADOR_POR_DEFECTO="Equipo # 3"
UMBRAL_CONFIANZA=60
UMBRAL_MARGEN=15
API_KEY=
```

> El host directo `db.<ref>.supabase.co` es **IPv6-only**; usa el pooler IPv4.
> El controlador debe ser `psycopg2` (SQLAlchemy 2.x usa `psycopg` v3 por defecto).
>
> `UMBRAL_CONFIANZA` y `UMBRAL_MARGEN` (en %) definen cuándo una predicción se
> marca como **“requiere revisión humana”**. `API_KEY` es opcional: si se define,
> hay que exportar el mismo valor en el frontend como `VITE_API_KEY` (`.env` de la
> raíz) para poder entrenar, activar versiones, importar CSV y etiquetar.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/macOS
cd ..
```

Aplica las migraciones (crea las tablas y siembra las 8 categorías):

```bash
npm run migrate
```

### 3. Importar etiquetas (CSV de Google Sheets)

CSV con columnas `ID, Solicitud, Categoría, Prioridad`. Hay un ejemplo de 80 filas
en `backend/data/etiquetas_ejemplo.csv`.

```bash
npm run importar                                   # usa el CSV de ejemplo
npm run importar -- data/mi_archivo.csv             # CSV guardado en backend/data/
```

Las filas inválidas se reportan sin abortar la importación y los textos duplicados
se omiten.

### Cargar un lote nuevo (por ejemplo, 100 solicitudes)

1. Prepara un CSV con una fila por solicitud y estas columnas exactas:
   `ID,Solicitud,Categoría,Prioridad`. La categoría debe corresponder a una de las
   8 categorías del sistema y la prioridad debe ser `ALTA`, `MEDIA` o `BAJA`.
   Registra etiquetas revisadas por una persona; no uses predicciones del modelo
   como si fueran etiquetas verdaderas.
2. Guarda el archivo, por ejemplo, como
   `backend/data/nuevas_100.csv` en UTF-8. Reparte los casos entre categorías y
   prioridades en la medida que tus datos reales lo permitan. Como referencia,
   el sistema considera insuficientes las clases con menos de 30 ejemplos y la
   guía propone una meta de 50 por categoría; no inventes casos para completar
   esas metas.
3. Desde la raíz del proyecto, impórtalo:

   ```bash
   npm run importar -- data/nuevas_100.csv
   ```

   El script se ejecuta desde `backend/`, por eso la ruta `data/...` es relativa a
   esa carpeta. El resumen indica cuántas filas se importaron, se omitieron por
   texto duplicado o fueron inválidas. El campo `ID` identifica la fila del CSV;
   el sistema evita duplicados comparando el texto normalizado, incluso contra
   solicitudes que ya existen en Supabase. Revisa el resumen antes de continuar.
4. Entrena con las etiquetas disponibles desde el panel **Modelo Agente →
   REENTRENAR AGENTE**. Alternativamente, con la API levantada:

   ```powershell
   Invoke-RestMethod -Method Post `
     -Uri "http://127.0.0.1:8000/api/modelo/entrenar" `
     -ContentType "application/json" `
     -Body '{"forzar":false,"etiquetado_por":"Equipo # 3"}'
   ```

   Si `API_KEY` está configurada, la petición también requiere la cabecera
   `X-API-Key`; no guardes ni compartas la clave en el repositorio. El sistema
   entrena sin el conjunto de prueba fijo, registra una versión nueva y solo la
   activa automáticamente si la comparación es válida y cumple la regla de F1.
   Una versión no activada queda en el historial para revisión.
5. Genera el informe actualizado desde la raíz:

   ```bash
   npm run informe
   ```

   El archivo se genera en `backend/reporte/datos_informe.md`. Para mostrarlo en
   el editor de VS Code puedes ejecutar `code backend/reporte/datos_informe.md`.
   El informe toma sus cifras de Supabase y del modelo; vuelve a generarlo después
   de importar y entrenar para presentar los resultados más recientes.

Las solicitudes creadas en el kiosco que aún no tienen una etiqueta verdadera se
revisan en **Panel administrativo → Etiquetado**. Allí se confirma o corrige cada
caso, y esa etiqueta humana queda disponible para el siguiente entrenamiento.
Importar un CSV con categoría y prioridad ya equivale a entregar filas etiquetadas:
no es necesario volver a etiquetarlas en esa pantalla.

### 4. Entrenar el agente

Desde la interfaz (**Modelo → REENTRENAR AGENTE**, pestaña **Prueba del agente** para
probar predicciones) o por API (`POST /api/modelo/entrenar`). Se comparan Naive Bayes
Multinomial, Regresión Logística y LinearSVC calibrado con validación cruzada
**agrupada** (por grupos de casi-duplicados) y se elige el mejor por **F1 macro**. Los
hiperparámetros (`C`, `alpha`, `ngram_range`, `min_df`) se ajustan con `GridSearchCV`
sobre las mismas particiones agrupadas. Una versión nueva solo se activa si **mejora o
iguala** el F1 macro de la versión activa **medido sobre el mismo conjunto de prueba**.

Se entrenan **dos clasificadores**: la **categoría** (8 clases) y la **prioridad**
(ALTA/MEDIA/BAJA); ambos reportan sus métricas, matrices de confusión y baselines.

Si ya existían versiones antiguas, se pueden **reevaluar todas** sobre el conjunto de
prueba fijo actual con `POST /api/modelo/reevaluar` (así el historial queda comparable).

### 5. Frontend

```bash
npm install
npm run dev        # http://localhost:5173
```

## Cómo se evalúa el agente (evitar métricas infladas)

1. **Fuga de datos por casi-duplicados.** Antes de dividir, los textos casi iguales
   (similitud coseno **TF-IDF ≥ 0.85**) se agrupan con *union-find*. La partición
   entrenamiento/prueba se hace **por grupos** (`StratifiedGroupKFold`), de modo que
   variantes de la misma frase **nunca** caen a la vez en entrenamiento y prueba. Sin
   esto, dos reformulaciones del mismo reclamo inflarían artificialmente el F1.
2. **Conjunto de prueba fijo.** Se reserva el **20 %** estratificado por categoría y por
   grupos (~116 casos con ~580 etiquetas). Todas las versiones se miden sobre el **mismo**
   conjunto (`version_prueba` = `prueba-gN`), así el historial es comparable y la
   activación solo compara métricas homogéneas. Al regenerarlo hay que reevaluar las
   versiones previas (`POST /api/modelo/reevaluar`).
3. **Baselines.** Se calcula el desempeño de (a) predecir siempre la **clase
   mayoritaria** y (b) **clasificación aleatoria estratificada**, para demostrar que el
   agente **supera el azar**.
4. **Calibración.** La tabla de fiabilidad por rangos de confianza y el **Brier score /
   ECE** permiten afirmar que “70 % de confianza” ≈ 70 % de acierto.
5. **Revisión humana (aprendizaje activo).** Si la confianza o el margen entre las dos
   clases más probables caen por debajo de los umbrales, la predicción se marca como
   **requiere revisión humana** en vez de forzar una categoría dudosa. El umbral se elige
   con la **curva cobertura-precisión** del conjunto de prueba.
6. **Mejora demostrable.** `npm run demo` submuestrea **estratíficamente** el pool de
   entrenamiento al 10/25/50/75/100 %, repite con **5 semillas** y reporta **media ±
   desviación estándar** del F1 y accuracy, siempre sobre el mismo conjunto de prueba
   (“a más etiquetas, mejor agente”).
7. **Acuerdo entre etiquetadores.** `GET /api/acuerdo-etiquetadores` calcula la **kappa de
   Cohen** sobre las solicitudes etiquetadas por 2+ personas y lista las discrepancias.
8. **Trazabilidad del entrenamiento (sin fuga de datos).** Cada versión guarda en
   `modelos.ids_entrenamiento` (JSONB) los **ids exactos** de las solicitudes con las que
   se entrenó. Una versión solo se considera **comparable** si esos ids **no intersectan**
   con el conjunto de prueba fijo (`valida_para_comparacion=true`). Las que sí intersectan
   quedan `valida_para_comparacion=false`, con motivo *“entrenada con datos del conjunto
   de prueba”*, **no aparecen** en la evolución del informe y **no pueden activarse** sin
   `?forzar=true`. Así se detecta y excluye cualquier métrica contaminada (p. ej. versiones
   antiguas que entrenaban con parte del conjunto de prueba y daban 100 %).
9. **Conjunto de prueba EXTERNO.** Además del conjunto fijo, se importan solicitudes
   nuevas con origen `prueba_externa` (`npm run importar -- data/prueba_externa.csv
   --origen prueba_externa`) que **nunca** se usan para entrenar. Sus métricas se reportan
   **aparte** en la pestaña *Modelo* y en `datos_informe.md`: son la prueba más honesta de
   generalización y pueden ser **más bajas** que las del conjunto fijo.

### Modelo de evaluación vs. modelo final de producción

- **Modelo de evaluación (el que versiona el sistema).** Se entrena **sin** el conjunto de
  prueba fijo (y sin el conjunto externo). Es el único que puede compararse de forma justa
  entre versiones, porque tanto entrenamiento como prueba son disjuntos; por eso el
  versionado, la activación y el informe usan este modelo.
- **Modelo final de producción (hipotético).** Una vez elegida la configuración ganadora,
  el modelo definitivo se podría **reentrenar con TODAS** las etiquetas (incluido el
  conjunto de prueba, que ya cumplió su función durante el desarrollo). Al reentrenar con
  todo, **ya no habría forma de medirlo con honestidad**, así que se conserva el modelo de
  evaluación como referencia de calidad y solo se lleva a producción el reentrenado cuando
  el proyecto se cierra.

> En resumen: se **mide** con el modelo de evaluación (sin fuga) y se **despliega**
> (al final) con un reentrenamiento sobre todo. Nunca se reportan métricas del modelo
> reentrenado sobre datos que ya vio.

## Catálogo de ecuaciones (Ec.1–Ec.20)

Numeración **estable** (no cambiar el orden ni los números) usada de forma consistente en
la interfaz, en la traza de inferencia y en el informe. La fuente única del frontend es
`src/lib/ecuaciones.ts`.

| Bloque | Ecuaciones | Tema |
|--------|-----------|------|
| Representación del texto | Ec.1–Ec.3 | TF, IDF y peso TF-IDF con normalización L2 |
| Clasificador lineal | Ec.4–Ec.5 | Puntaje de decisión y objetivo del SVM |
| Calibración | Ec.6–Ec.7 | Sigmoide de Platt y normalización de probabilidades |
| Decisión | Ec.8–Ec.9 | Margen y umbrales de revisión humana |
| Métricas de evaluación | Ec.10–Ec.16 | Accuracy, precisión, recall, F1, F1 macro, Brier y ECE |
| Incertidumbre y acuerdo | Ec.17–Ec.18 | Intervalo de Wilson y kappa de Cohen |
| Modelos alternativos | Ec.19–Ec.20 | Naive Bayes multinomial y Softmax |

| # | Ecuación | Fórmula |
|---|----------|---------|
| 1 | Frecuencia del término (TF) | tf(t, d) = nº de veces que t aparece en d |
| 2 | Frecuencia inversa de documento (IDF) | idf(t) = ln((1 + N) / (1 + df(t))) + 1 |
| 3 | Peso TF-IDF y norma L2 | tfidf(t, d) = tf(t, d)·idf(t); x̂ = x / ‖x‖₂ |
| 4 | Puntaje de decisión lineal | s_c(x) = w_c·x + b_c |
| 5 | Objetivo del SVM | mín ½‖w‖² + C·Σξᵢ  s.a. yᵢ(w·xᵢ + b) ≥ 1 − ξᵢ |
| 6 | Calibración de Platt | P(y = 1 \| s) = 1 / (1 + exp(A·s + B)) |
| 7 | Normalización de probabilidades | P(c \| x) = P̂(c \| x) / Σ P̂(c' \| x) |
| 8 | Margen de decisión | margen = P(c₁ \| x) − P(c₂ \| x) |
| 9 | Umbrales de decisión | aceptar ⇔ confianza ≥ 60 % ∧ margen ≥ 15 % |
| 10 | Exactitud (accuracy) | (VP + VN) / (VP + VN + FP + FN) |
| 11 | Precisión | VP / (VP + FP) |
| 12 | Exhaustividad (recall) | VP / (VP + FN) |
| 13 | F1 | 2·(precisión·recall) / (precisión + recall) |
| 14 | F1 macro | (1/K)·Σ F1_k |
| 15 | Brier score | BS = (1/N)·Σ (p̂ᵢ − yᵢ)² |
| 16 | Error de calibración esperado (ECE) | Σ (n_m / N)·\|acierto_m − confianza_m\| |
| 17 | Intervalo de confianza de Wilson | (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n) |
| 18 | Kappa de Cohen | κ = (p₀ − pₑ) / (1 − pₑ) |
| 19 | Naive Bayes multinomial | P(c \| x) ∝ P(c)·Π P(t \| c)^{x_t} |
| 20 | Softmax | P(c \| x) = exp(s_c(x)) / Σ exp(s_{c'}(x)) |

## Librerías y versiones

Backend (`backend/requirements.txt`, Python 3.12+ / probado con 3.14):

| Librería | Versión | Uso |
|----------|---------|-----|
| `fastapi` | 0.163.0 | API REST |
| `uvicorn[standard]` | 0.54.0 | Servidor ASGI |
| `sqlalchemy` | 2.1.8 | ORM (único acceso a la base de datos) |
| `psycopg2-binary` | 2.9.13 | Controlador PostgreSQL |
| `alembic` | 1.20.1 | Migraciones |
| `scikit-learn` | 1.9.1 | TF-IDF, clasificadores, métricas y calibración |
| `pandas` | 3.1.1 | Lectura de CSV |
| `python-dotenv` | 1.2.3 | Variables de entorno |
| `joblib` | 1.6.0 | Serialización de los modelos |
| `pytest` | 9.2.0 | Pruebas |
| `httpx` | 0.28.1 | Cliente HTTP de las pruebas |

Frontend (`package.json`): React 19, React DOM 19, Vite 8, TypeScript 5.7, Tailwind CSS 4
(con `@tailwindcss/vite`), `concurrently` y `oxfmt`.

## Scripts

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Servidor de desarrollo del frontend (Vite) |
| `npm run api` | API FastAPI en `http://127.0.0.1:8000` |
| `npm run dev:all` | Levanta API y frontend a la vez (`concurrently`) |
| `npm run build` | Comprobación de tipos (`tsc --noEmit`) + build de producción |
| `npm run migrate` | Aplica las migraciones Alembic |
| `npm run importar` | Importa etiquetas desde CSV |
| `npm run demo` | Demuestra la mejora del F1 al aumentar las etiquetas (10→100 %, 5 semillas) |
| `npm run informe` | Genera `backend/reporte/datos_informe.md` con toda la evidencia desde la BD |
| `npm run test:backend` | Ejecuta la suite de pruebas `pytest` |

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/salud` | Estado REAL: SELECT 1 en la BD, modelo activo, nº de etiquetas y umbrales |
| `GET` | `/api/categorias` | Catálogo de las 8 categorías |
| `POST` | `/api/solicitudes` | Crea una solicitud, predice y guarda (latencia medida + `requiere_revision`) |
| `GET` | `/api/solicitudes` | Lista con filtros (estado, categoría, etiquetada, confianza…) |
| `PATCH` | `/api/solicitudes/{id}/estado` | Cambia el estado |
| `PATCH` | `/api/solicitudes/{id}/asignar` | Asigna a una cuadrilla |
| `POST` | `/api/solicitudes/{id}/etiqueta` | Fija categoría y prioridad correctas · **requiere API key** |
| `POST` | `/api/solicitudes/importar` | Importa etiquetas desde CSV · **requiere API key** |
| `GET` | `/api/etiquetado/cola` | Cola priorizada (aprendizaje activo) |
| `GET` | `/api/etiquetado/guia` | Guía de criterios y metas |
| `POST` | `/api/modelo/entrenar` | Reentrena y decide la activación (opción `generar_informe`) · **requiere API key** |
| `GET` | `/api/modelo/activo` · `/versiones` · `/metricas` | Modelo y métricas reales |
| `GET` | `/api/modelo/parametros` | Parámetros reales del modelo activo (algoritmos, hiperparámetros, TF-IDF, división, umbrales y eficiencia) |
| `POST` | `/api/modelo/reevaluar` | Reevalúa todas las versiones sobre el conjunto de prueba actual · **requiere API key** |
| `POST` | `/api/modelo/{version}/activar` | Rollback a una versión anterior · **requiere API key** |
| `GET` | `/api/estadisticas` | Totales, progreso por categoría y por etiquetador |
| `GET` | `/api/calidad-dataset` | Informe de calidad (desbalance, duplicados, casi-duplicados, contradicciones) |
| `GET` | `/api/acuerdo-etiquetadores` | Kappa de Cohen y discrepancias entre etiquetadores |
| `GET` | `/api/experimentos` | Experimentos guardados (mejora por volumen de etiquetas) |
| `POST` | `/api/predecir` | Predicción sin guardar + **traza de las 11 etapas** (inspector NLP y Prueba del agente) |
| `POST` | `/api/informe/generar` | Genera y guarda el informe del agente (`.md` + `.json`) · **requiere API key** |
| `GET` | `/api/informe` | Historial de informes generados · **requiere API key** |
| `GET` | `/api/informe/{id}` · `/{id}/estado` | Contenido completo y estado de un informe · **requiere API key** |
| `GET` | `/api/informe/{id}/descargar?formato=md\|json\|zip` | Descarga el informe (el ZIP incluye los CSV de las matrices) · **requiere API key** |

Los endpoints marcados con **requiere API key** solo exigen la cabecera `X-API-Key` si la
variable `API_KEY` está definida en el backend.

## Pruebas

```bash
npm run test:backend
```

Cubren el preprocesamiento, que el entrenamiento **excluye el conjunto de prueba
fijo**, que **no se activa una versión peor**, la importación de CSV y los endpoints.
Además, `tests/test_agente.py` verifica la **traza de 11 etapas** y la coherencia con los
umbrales, los **parámetros del modelo activo** (`GET /api/modelo/parametros`) y el
**informe del agente** (generación, historial, descargas `.md`/`.json`/`.zip` y los CSV de
las matrices de confusión).

## Qué probar en la demostración

1. **Kiosco:** escribe un reclamo y comprueba que la categoría, la prioridad y la
   confianza provienen del modelo real (no hay valores fijos).
2. **Prueba del agente (pestaña nueva):** escribe una solicitud en vivo y muestra la
   categoría, la prioridad, la confianza, las **probabilidades de las 8 clases** y los
   **términos que más pesaron**. Prueba también un caso **ambiguo/fuera de dominio** para
   ver el aviso de *“requiere revisión humana”*.
3. **Inspector NLP:** abre la trazabilidad de una solicitud y revisa el pipeline
   completo (normalización, TF-IDF, términos que aportaron, decisión).
4. **Etiquetado:** confirma o corrige etiquetas; observa cómo la cola prioriza las
   predicciones más inciertas (menor confianza y menor margen).
5. **Modelo → REENTRENAR AGENTE:** compara las métricas de **categoría y prioridad**,
   los **baselines**, la **calibración**, la **curva cobertura-precisión** y el
   **análisis de errores**; prueba el *rollback* desde el historial.
6. **Mejora por volumen:** `npm run demo` (10 → 100 % de las etiquetas, 5 semillas,
   media ± desviación estándar) y revisa el gráfico en **Modelo**.
7. **Calidad y consistencia:** revisa en **Modelo** el informe de calidad del dataset
   (desbalance, casi-duplicados, contradicciones) y la **kappa de Cohen**.
8. **Soporte técnico:** abre *Soporte* y muestra el estado **real** leído de
   `/api/salud` (BD, modelo activo, nº de etiquetas y umbrales), sin textos fijos.

## Reglas del proyecto

- Ninguna credencial en el código, README ni commits: todo por variables de entorno.
- Nada simulado: cada número de la interfaz sale de la base de datos o de un
  entrenamiento real.
- Código comentado en español, TypeScript estricto y *type hints* en Python.
- Solo SQLAlchemy ORM (sin SQL propio de un motor) y RLS activo en todas las tablas.
