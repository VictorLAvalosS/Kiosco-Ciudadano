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
```

> El host directo `db.<ref>.supabase.co` es **IPv6-only**; usa el pooler IPv4.
> El controlador debe ser `psycopg2` (SQLAlchemy 2.x usa `psycopg` v3 por defecto).

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
npm run importar -- ruta/a/mi_archivo.csv          # usa tu archivo real
```

Las filas inválidas se reportan sin abortar la importación y los textos duplicados
se omiten.

### 4. Entrenar el agente

Desde la interfaz (**Modelo → REENTRENAR AGENTE**) o por API
(`POST /api/modelo/entrenar`). Se comparan Naive Bayes Multinomial, Regresión
Logística y LinearSVC calibrado con validación cruzada estratificada y se elige el
mejor por **F1 macro**. Una versión nueva solo se activa si **mejora o iguala** el
F1 macro de la versión activa (se puede forzar).

### 5. Frontend

```bash
npm install
npm run dev        # http://localhost:5173
```

## Scripts

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Servidor de desarrollo del frontend (Vite) |
| `npm run api` | API FastAPI en `http://127.0.0.1:8000` |
| `npm run dev:all` | Levanta API y frontend a la vez (`concurrently`) |
| `npm run build` | Comprobación de tipos (`tsc --noEmit`) + build de producción |
| `npm run migrate` | Aplica las migraciones Alembic |
| `npm run importar` | Importa etiquetas desde CSV |
| `npm run demo` | Demuestra la mejora del F1 al aumentar las etiquetas |
| `npm run test:backend` | Ejecuta la suite de pruebas `pytest` |

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/salud` | Disponibilidad del servicio |
| `GET` | `/api/categorias` | Catálogo de las 8 categorías |
| `POST` | `/api/solicitudes` | Crea una solicitud, predice y guarda (latencia medida) |
| `GET` | `/api/solicitudes` | Lista con filtros (estado, categoría, etiquetada, confianza…) |
| `PATCH` | `/api/solicitudes/{id}/estado` | Cambia el estado |
| `PATCH` | `/api/solicitudes/{id}/asignar` | Asigna a una cuadrilla |
| `POST` | `/api/solicitudes/{id}/etiqueta` | Fija categoría y prioridad correctas |
| `POST` | `/api/solicitudes/importar` | Importa etiquetas desde CSV |
| `GET` | `/api/etiquetado/cola` | Cola priorizada (aprendizaje activo) |
| `GET` | `/api/etiquetado/guia` | Guía de criterios y metas |
| `POST` | `/api/modelo/entrenar` | Reentrena y decide la activación |
| `GET` | `/api/modelo/activo` · `/versiones` · `/metricas` | Modelo y métricas reales |
| `POST` | `/api/modelo/{version}/activar` | Rollback a una versión anterior |
| `GET` | `/api/estadisticas` | Totales, progreso por categoría y por etiquetador |
| `POST` | `/api/predecir` | Predicción sin guardar (inspector NLP) |

## Pruebas

```bash
npm run test:backend
```

Cubren el preprocesamiento, que el entrenamiento **excluye el conjunto de prueba
fijo**, que **no se activa una versión peor**, la importación de CSV y los endpoints.

## Qué probar en la demostración

1. **Kiosco:** escribe un reclamo y comprueba que la categoría, la prioridad y la
   confianza provienen del modelo real (no hay valores fijos).
2. **Inspector NLP:** abre la trazabilidad de una solicitud y revisa el pipeline
   completo (normalización, TF-IDF, términos que aportaron, decisión).
3. **Etiquetado:** confirma o corrige etiquetas; observa cómo la cola prioriza las
   predicciones más inciertas (menor confianza y menor margen).
4. **Modelo → REENTRENAR AGENTE:** compara las métricas y la nueva versión frente a
   la anterior; prueba el *rollback* desde el historial.
5. **Demo de mejora:** `npm run demo` (20 % → 50 % → 100 % de las etiquetas).

## Reglas del proyecto

- Ninguna credencial en el código, README ni commits: todo por variables de entorno.
- Nada simulado: cada número de la interfaz sale de la base de datos o de un
  entrenamiento real.
- Código comentado en español, TypeScript estricto y *type hints* en Python.
- Solo SQLAlchemy ORM (sin SQL propio de un motor) y RLS activo en todas las tablas.
