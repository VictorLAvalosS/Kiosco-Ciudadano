# Backend y agente de clasificación


## 2. Dónde está el agente

En este proyecto, “agente” es el nombre de la interfaz para el **pipeline de clasificación supervisada**. No es un chatbot ni un modelo de lenguaje generativo. Sus piezas principales están aquí:

- `backend/ml/preprocesamiento.py`: normaliza texto en español y elimina stopwords.
- `backend/ml/entrenamiento.py`: construye, compara y evalúa modelos TF-IDF más clasificadores.
- `backend/ml/inferencia.py`: predice categoría/prioridad, calcula confianza y margen, y prepara explicaciones.
- `backend/app/servicio_modelo.py`: orquesta carga de etiquetas, entrenamiento, versionado, activación, carga del modelo activo e inferencia desde la aplicación.
- `backend/app/routers/predecir.py`: expone una predicción de prueba sin guardar una solicitud.
- `backend/app/routers/solicitudes.py`: clasifica y persiste una solicitud nueva.
- `backend/app/routers/modelo.py`: expone entrenamiento, versiones, métricas y activación/rollback.

El artefacto entrenado se serializa con `joblib` y su binario se guarda en la tabla `modelos` de PostgreSQL (columna `modelo_binario`). El servicio mantiene además una caché por versión en memoria. Por eso, el código del agente vive en `backend/ml/` y `backend/app/servicio_modelo.py`, mientras que el modelo ya entrenado vive en la base de datos; no hay un archivo de pesos fijo dentro del repositorio.

## 3. Recorrido de una solicitud

1. El frontend envía el texto a `POST /api/solicitudes` (para registrar) o `POST /api/predecir` (solo probar).
2. FastAPI valida el cuerpo con los esquemas de `backend/app/schemas.py` y abre una sesión por petición mediante `backend/app/database.py`.
3. `servicio_modelo.py` obtiene la versión activa y la deserializa si no está en caché.
4. `ml/preprocesamiento.py` pasa el texto a minúsculas, quita tildes y puntuación, compacta espacios, tokeniza y elimina palabras comunes.
5. El pipeline TF-IDF convierte palabras y n-gramas en valores numéricos. Dos clasificadores predicen categoría municipal y prioridad (ALTA, MEDIA o BAJA).
6. `ml/inferencia.py` devuelve rankings de probabilidad, confianza, margen entre las dos categorías principales y contribuciones de términos cuando el algoritmo permite explicarlas.
7. La confianza y el margen se comparan con `UMBRAL_CONFIANZA` y `UMBRAL_MARGEN` (por defecto 60 y 15). Si no alcanza cualquiera, el caso se marca para revisión humana.
8. La ruta de solicitudes guarda resultado, versión, probabilidades, tiempo de inferencia y estado mediante SQLAlchemy. `/predecir` solo devuelve la explicación y no registra una solicitud.

La traza educativa de 11 etapas se construye en `ml/inferencia.py` y se usa en la pestaña “Prueba del agente”.

## 4. Cómo aprende y mejora

Las etiquetas humanas de categoría y prioridad son los ejemplos supervisados. `backend/app/servicio_solicitudes.py` conserva el historial: una corrección marca la etiqueta anterior como no vigente y registra la nueva. El entrenamiento usa las etiquetas vigentes y excluye el origen `prueba_externa`.

Al llamar `POST /api/modelo/entrenar`, `servicio_modelo.py` compara tres opciones (Naive Bayes Multinomial, Regresión Logística y LinearSVC calibrado), ajusta hiperparámetros y entrena modelos separados para categoría y prioridad. La evaluación utiliza un conjunto fijo de prueba cuando está disponible; se separan grupos de textos casi duplicados para reducir fuga de datos. Si aún no existe suficiente historial, se usa validación cruzada. Se guardan métricas como accuracy, precisión, recall, F1 macro, matrices de confusión, curva de aprendizaje, análisis de errores y eficiencia.

La nueva versión queda registrada en `modelos`. El servicio aplica su regla de activación comparándola con la versión vigente sobre datos comparables; el endpoint también permite activar una versión anterior. El sistema solicita al menos 8 etiquetas para iniciar entrenamiento, aunque eso no significa que haya suficientes ejemplos por clase para métricas estables: la meta configurada para considerar suficiente cobertura es 30 por clase.

## 5. Componentes del backend

| Ruta | Responsabilidad |
| --- | --- |
| `backend/app/main.py` | Crea FastAPI, configura CORS y registra routers bajo `/api`. |
| `backend/app/config.py` | Lee variables del entorno y `backend/.env`; centraliza URL de BD, CORS, umbrales y clave API. |
| `backend/app/database.py` | Crea motor y sesiones de SQLAlchemy. |
| `backend/app/models.py` | Define tablas ORM: categorías, solicitudes, etiquetas, modelos, prueba fija, etiquetadores, experimentos e informes. |
| `backend/app/schemas.py` | Define validación y formatos de entrada/salida de la API. |
| `backend/app/serializadores.py` | Convierte filas ORM a respuestas de API. |
| `backend/app/seguridad.py` | Comprueba `X-API-Key` si se configuró `API_KEY`. |
| `backend/app/routers/` | Endpoints de solicitudes, etiquetado, modelo, estadísticas, predicción, sistema e informes. |
| `backend/app/servicio_solicitudes.py` | Reglas de solicitudes, etiquetas e importación CSV. |
| `backend/app/servicio_modelo.py` | Flujo de entrenamiento e inferencia/versiones del agente. |
| `backend/app/servicio_informe.py` | Genera informes Markdown/JSON a partir del estado del sistema. |
| `backend/ml/` | Preprocesamiento, entrenamiento, inferencia y análisis de calidad. |
| `backend/alembic/` | Migraciones de esquema y configuración RLS. |
| `backend/tests/` | Pruebas automatizadas con pytest. |

## 6. Datos y seguridad

Las tablas se declaran con SQLAlchemy en `models.py`; las migraciones de Alembic en `backend/alembic/versions/` crean y actualizan el esquema. La migración inicial define las tablas y habilita RLS en las tablas de datos indicadas por el proyecto. El backend es el cliente de base de datos y el frontend consume la API.

La configuración de conexión se obtiene de `backend/.env`, tomando como referencia `backend/.env.example`. No copiar credenciales a documentación ni código. `API_KEY` es opcional; cuando se establece, las rutas sensibles que declaran `verificar_api_key` exigen la cabecera `X-API-Key`. La política efectiva de acceso desde Supabase también depende de las políticas RLS configuradas para el rol usado por la conexión.

## 7. Endpoints principales

- `GET /api/salud`: estado de conexión, versión activa y conteo de etiquetas.
- `POST /api/predecir`: prueba el pipeline sin guardar.
- `POST /api/solicitudes` y `GET /api/solicitudes`: registra y consulta solicitudes.
- `POST /api/solicitudes/{id}/etiqueta`: registra/corrige etiqueta humana.
- `GET /api/etiquetado/cola`: prioriza casos sin etiquetar y con predicción incierta.
- `POST /api/modelo/entrenar`, `GET /api/modelo/activo`, `GET /api/modelo/versiones`: ciclo del modelo.
- `GET /api/estadisticas`, `GET /api/calidad-dataset`, `GET /api/acuerdo-etiquetadores`: seguimiento del dataset y etiquetado.
- `/api/informe`: generación, consulta e historial de informes.

La lista completa y los parámetros están descritos por FastAPI en `/docs` mientras la API está ejecutándose.

## 8. Cómo arrancarlo

Desde la raíz del proyecto, según los scripts de `package.json`:

```powershell
npm run api       # solo backend en 127.0.0.1:8000
npm run dev:all   # backend y frontend
npm run migrate   # aplicar migraciones Alembic
npm run test:backend # ejecutar pytest del backend
```

La API lee su configuración de `backend/.env`. Para usar Supabase, debe existir `DATABASE_URL` con el controlador `postgresql+psycopg2://`. El proxy de Vite reenvía `/api` al puerto 8000.

## 9. Cómo orientarse en el código

Para seguir una predicción, empieza por `backend/app/routers/predecir.py`, continúa en `backend/app/servicio_modelo.py` (`predecir_con_explicacion` y `predecir_texto`) y termina en `backend/ml/inferencia.py`. Para seguir el aprendizaje, empieza por `backend/app/routers/modelo.py` y sigue a `entrenar_nueva_version` en `servicio_modelo.py`, luego a `backend/ml/entrenamiento.py`. Para entender la persistencia, revisa `backend/app/models.py`, `backend/app/database.py` y las migraciones de Alembic.
