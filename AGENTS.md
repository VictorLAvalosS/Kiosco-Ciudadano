# Kiosco Ciudadano · Panel Administrativo

Aplicación **React + Vite + TypeScript + Tailwind CSS** para la gestión de solicitudes
ciudadanas de las Organizaciones Territoriales de Base (OTB). Las solicitudes se
clasifican automáticamente por **aprendizaje supervisado (NLP)** con un modelo
entrenado **realmente** sobre datos etiquetados almacenados en **PostgreSQL (Supabase)**.

## Arquitectura

- **Frontend** (`src/`): React 19 + Vite 8. Consume la API del backend por `fetch`
  (`/api`), usando el proxy de Vite hacia `http://127.0.0.1:8000`. **Nunca** se
  conecta directamente a la base de datos.
- **Backend** (`backend/`): FastAPI + SQLAlchemy 2 (ORM) + Alembic + scikit-learn.
  Es el **único cliente** de la base de datos.
- **Base de datos**: PostgreSQL en Supabase, con **Row Level Security (RLS)** activo
  en todas las tablas.

## Servidor de desarrollo

```bash
npm install
npm run dev        # frontend en http://localhost:5173 (o $PORT)
npm run api        # API FastAPI en http://127.0.0.1:8000
npm run dev:all    # ambos a la vez (concurrently)
npm run build      # tsc --noEmit + build de producción
npm run preview    # previsualización de la build
```

Comandos del backend:

```bash
npm run migrate         # aplica las migraciones Alembic
npm run importar        # importa etiquetas desde CSV
npm run demo            # demuestra la mejora del F1 según el volumen de etiquetas
npm run test:backend    # ejecuta pytest
```

## Variables de entorno

La conexión a Supabase se lee **solo** de `backend/.env` (plantilla:
`backend/.env.example`). El archivo `.env` está en `.gitignore`.

- `DATABASE_URL` — cadena del *Session pooler* de Supabase (IPv4).
  Debe usar el controlador `postgresql+psycopg2://`.
- `CORS_ORIGINS` — origen permitido para el frontend de Vite.
- `ETIQUETADOR_POR_DEFECTO` — nombre por defecto del integrante que etiqueta.

**Prohibido** escribir credenciales en el código, en el README o en commits.

## Estructura del proyecto

### Frontend

- `src/main.tsx` - Punto de entrada React; importa `src/index.css` y monta `src/App.tsx` en `#root`
- `src/App.tsx` - Componente raíz; navegación entre kiosco, análisis, resultado y panel
- `src/index.css` - Entrada global de CSS (Tailwind CSS v4) y estilos de los componentes
- `src/types.ts` - Tipos compartidos (solicitudes, categorías, modelo, estadísticas, cola de etiquetado)
- `src/lib/api.ts` - Cliente HTTP de la API (funciones por endpoint, `ApiError`)
- `src/lib/catalogos.ts` - Catálogos de la interfaz (OTB, cuadrillas) y utilidades de formato
- `src/components/` - Interfaz: `Kiosk`, `Processing`, `Result`, `Dashboard`,
  `OperationsModules` (mapa y cuadrillas), `EtiquetadoPage`, `ModelPage`, `NlpInspector`, `Icon`, `shared`
- `vite.config.ts` - Configuración de Vite (React, Tailwind v4, alias `@`, proxy `/api`)
- `index.html` - Contenedor HTML de Vite con el elemento `#root`

### Backend

- `backend/app/main.py` - Aplicación FastAPI (CORS + routers bajo `/api`)
- `backend/app/config.py` - Lectura de variables de entorno (`DATABASE_URL`, `CORS_ORIGINS`)
- `backend/app/database.py` - Motor y sesión de SQLAlchemy
- `backend/app/models.py` - Modelos ORM: `categorias`, `solicitudes`, `etiquetas`,
  `modelos`, `conjunto_prueba_fijo`, `usuarios_etiquetadores`
- `backend/app/categorias.py` - Las 8 categorías fijas, prioridades y estados válidos
- `backend/app/routers/` - Endpoints: `solicitudes`, `etiquetado`, `modelo`, `estadisticas`, `predecir`
- `backend/app/servicio_solicitudes.py` - Ticket, etiquetas (con historial `vigente`), importación CSV
- `backend/app/servicio_modelo.py` - Entrenamiento, versionado, activación y rollback
- `backend/ml/` - `preprocesamiento` (normalización, stopwords), `entrenamiento` (TF-IDF,
  comparación de algoritmos, métricas, curva de aprendizaje) e `inferencia` (predicción, explicabilidad)
- `backend/alembic/` - Migraciones de la base de datos
- `backend/data/etiquetas_ejemplo.csv` - CSV de ejemplo (planilla de Google Sheets)
- `backend/importar_csv.py` - Importación por línea de comandos
- `backend/demo_mejora.py` - Demostración de la mejora por volumen de etiquetas
- `backend/tests/` - Pruebas `pytest`

## Dependencias

- Runtime frontend: React 19 y React DOM 19
- Estilizado: Tailwind CSS v4 con el plugin `@tailwindcss/vite`
- Herramientas frontend: Vite 8, TypeScript 5.7, `@vitejs/plugin-react`, `concurrently`, oxfmt
- Backend: FastAPI, SQLAlchemy, psycopg2-binary, Alembic, scikit-learn, joblib, pandas
- Pruebas backend: pytest, httpx

## Estilizado

El proyecto usa **Tailwind CSS v4** mediante el plugin `@tailwindcss/vite` configurado en
`vite.config.ts`. `src/index.css` importa Tailwind con `@import 'tailwindcss';`. La mayor parte
del diseño se construye con clases utilitarias de Tailwind en JSX y con CSS global en
`src/index.css`; no se necesita archivo de configuración de Tailwind ni PostCSS.

Mantén las sentencias CSS `@import` al inicio del archivo y sitúa los estilos globales de
elementos dentro de `@layer base { ... }` para que las utilidades de Tailwind sigan aplicándose.

## Reglas

- Ninguna credencial en el código: todo por variables de entorno.
- Nada simulado: cada número de la interfaz sale de la base de datos o de un entrenamiento real.
- Solo SQLAlchemy ORM (sin SQL propio de un motor) y RLS activo en todas las tablas.
- Código comentado en español, TypeScript estricto y *type hints* en Python.
