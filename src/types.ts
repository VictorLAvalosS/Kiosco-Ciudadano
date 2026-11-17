/**
 * Tipos compartidos del frontend del Kiosco Ciudadano.
 *
 * Reflejan EXACTAMENTE lo que devuelve la API del backend (FastAPI + Supabase).
 * No existe estado local simulado: todo dato proviene de la base de datos.
 */

/** Iconos SVG disponibles (deben existir en components/Icon.tsx). */
export type IconName =
  | "arrow"
  | "bolt"
  | "check"
  | "chevron"
  | "clock"
  | "copy"
  | "dashboard"
  | "droplet"
  | "factory"
  | "grid"
  | "headset"
  | "leaf"
  | "lightbulb"
  | "map"
  | "mic"
  | "moon"
  | "printer"
  | "road"
  | "search"
  | "settings"
  | "shield"
  | "sun"
  | "trash"
  | "users"
  | "waves";

export type Priority = "ALTA" | "MEDIA" | "BAJA";

export type RequestStatus = "Sin asignar" | "En proceso" | "Asignado" | "Resuelto";

export type RequestOrigin = "kiosco" | "importado" | "panel" | "prueba_externa";

/** Categoría municipal (tabla `categorias`). */
export interface Categoria {
  id: number;
  clave: string;
  nombre: string;
  departamento: string;
  icono: string;
}

/** Probabilidad de una clase devuelta por el clasificador. */
export interface Probabilidad {
  clase: string;
  probabilidad: number;
}

/** Término que contribuyó a una predicción (coeficiente × tf-idf). */
export interface Contribucion {
  termino: string;
  contribucion: number;
  tfidf: number;
}

/** Etiqueta correcta asignada por una persona del equipo. */
export interface Etiqueta {
  id: number;
  categoria_id: number;
  categoria_clave: string;
  categoria_nombre: string;
  prioridad: Priority;
  etiquetado_por: string;
  fecha: string;
  vigente: boolean;
}

/** Solicitud ciudadana con la predicción del modelo activo. */
export interface Solicitud {
  id: number;
  ticket: string;
  texto: string;
  otb: string;
  zona: string;
  fecha: string;
  estado: RequestStatus;
  origen: RequestOrigin;
  categoria_predicha_id: number | null;
  categoria_predicha_clave: string | null;
  categoria_predicha_nombre: string | null;
  categoria_predicha_departamento: string | null;
  categoria_predicha_icono: string | null;
  prioridad_predicha: Priority | null;
  confianza: number | null;
  probabilidades: Probabilidad[] | null;
  version_modelo: string | null;
  latencia_ms: number | null;
  requiere_revision: boolean;
  prediccion_detalle?: Prediccion | null;
  etiquetada: boolean;
  etiqueta: Etiqueta | null;
}

/** Término del documento con su peso TF-IDF real (traza, Ec.1–3). */
export interface TerminoTfidf {
  termino: string;
  tf: number;
  idf: number;
  tfidf: number;
}

/** Puntaje de decisión por clase s_c(x) = w_c·x + b_c (traza, Ec.4). */
export interface PuntajeClase {
  clase: string;
  puntaje: number;
}

/** Decisión final de la traza: comparación con los umbrales (Ec.9). */
export interface DecisionTraza {
  confianza: number;
  umbral_confianza: number;
  cumple_confianza: boolean;
  margen: number;
  umbral_margen: number;
  cumple_margen: boolean;
  resultado: "automatica" | "revision_humana";
  categoria: string;
  prioridad: string;
}

/** Resumen equivalente de la traza para el clasificador de prioridad (Ec.11). */
export interface BloquePrioridadTraza {
  clase: string;
  puntajes: PuntajeClase[];
  probabilidades: Probabilidad[];
  confianza: number;
  margen: number;
}

/**
 * Traza didáctica con las 11 etapas reales del agente (Fase A1).
 *
 * Proviene de `backend/ml/inferencia.py:construir_traza` y refleja cada paso
 * intermedio del pipeline con datos reales del modelo activo.
 */
export interface TrazaAgente {
  texto_original: string;
  texto_normalizado: string;
  tokens: string[];
  tokens_sin_stopwords: string[];
  stopwords_eliminadas: string[];
  n_gramas: string[];
  terminos_tfidf: TerminoTfidf[];
  puntajes_categoria: PuntajeClase[];
  probabilidades_categoria: Probabilidad[];
  confianza_categoria: number;
  margen_categoria: number;
  decision: DecisionTraza;
  prioridad: BloquePrioridadTraza;
}

/** Resultado completo del pipeline NLP (endpoint /api/predecir). */
export interface Prediccion {
  texto: string;
  texto_normalizado: string;
  tokens: string[];
  tokens_originales: string[];
  stopwords: number;
  categoria: string;
  categoria_nombre: string;
  departamento: string;
  icono: string;
  prioridad: Priority;
  confianza: number;
  margen: number;
  probabilidades: Probabilidad[];
  probabilidades_prioridad: Probabilidad[];
  contribuciones: Contribucion[];
  version_modelo: string;
  algoritmo: string;
  latencia_ms: number;
  requiere_revision: boolean;
  umbral_confianza: number;
  umbral_margen: number;
  /** Traza didáctica de las 11 etapas (Fase A1); puede faltar en respuestas antiguas. */
  traza: TrazaAgente | null;
}

/** Métricas por clase del modelo. */
export interface MetricaClase {
  precision: number;
  recall: number;
  f1: number;
  soporte: number;
}

/** Punto de la curva cobertura-precisión (elección del umbral de revisión). */
export interface PuntoCobertura {
  umbral: number;
  n: number;
  cobertura: number;
  precision: number | null;
}

/** Fila de la tabla de fiabilidad (calibración de la confianza). */
export interface FilaCalibracion {
  rango: [number, number];
  n: number;
  confianza_media: number | null;
  exactitud: number | null;
}

/** Caso mal clasificado del conjunto de prueba. */
export interface ErrorClasificacion {
  texto: string;
  real: string;
  predicha: string;
  confianza: number;
}

/** Bloque de evaluación ampliada guardado en `modelos.evaluacion` (JSONB). */
export interface EvaluacionModelo {
  baselines_categoria?: Record<string, unknown>;
  baselines_prioridad?: Record<string, unknown>;
  calibracion_categoria?: {
    tabla?: FilaCalibracion[];
    brier?: number | null;
    ece?: number | null;
    n?: number;
  };
  curva_cobertura_precision?: PuntoCobertura[];
  errores_categoria?: ErrorClasificacion[];
  casi_duplicados?: {
    umbral?: number;
    n_grupos?: number;
    n_casi_duplicados?: number;
    registros_extra?: number;
    n_grupos_con_duplicados?: number;
  };
  matriz_confusion_prioridad?: {
    etiquetas?: string[];
    matriz?: number[][];
    pares_confundidos?: { real: string; predicha: string; casos: number }[];
  };
  metricas_por_clase_prioridad?: Record<string, MetricaClase>;
  umbrales_revision?: { confianza?: number; margen?: number };
  version_prueba?: string;
  metodo_evaluacion?: string;
  n_etiquetas?: number;
  /** Métricas sobre el conjunto de prueba EXTERNO (nunca usado al entrenar). */
  prueba_externa?: {
    n?: number;
    accuracy?: number;
    precision_macro?: number;
    recall_macro?: number;
    f1_macro?: number;
    accuracy_prioridad?: number;
    f1_prioridad?: number;
    metricas_por_clase?: Record<string, MetricaClase>;
    matriz_confusion?: { etiquetas?: string[]; matriz?: number[][] };
  };
}

/** Versión entrenada del modelo (tabla `modelos`). */
export interface Modelo {
  id: number;
  version: string;
  fecha: string;
  algoritmo: string;
  hiperparametros: Record<string, unknown>;
  n_entrenamiento: number;
  n_validacion: number;
  n_prueba: number;
  accuracy: number;
  precision_macro: number;
  recall_macro: number;
  f1_macro: number;
  matriz_confusion: {
    etiquetas?: string[];
    matriz?: number[][];
    pares_confundidos?: { real: string; predicha: string; casos: number }[];
  };
  metricas_por_clase: Record<string, MetricaClase>;
  curva_aprendizaje: {
    tamanos?: number[];
    f1_validacion?: number[];
    f1_entrenamiento?: number[];
  };
  top_terminos: Record<string, { termino: string; peso: number }[]>;
  version_prueba: string;
  metodo_evaluacion: string;
  accuracy_prioridad: number;
  precision_prioridad: number;
  recall_prioridad: number;
  f1_prioridad: number;
  evaluacion: EvaluacionModelo;
  /** Eficiencia medida realmente (Fase A3): tiempo, tamaño y latencia. */
  eficiencia: EficienciaModelo;
  /** Trazabilidad del entrenamiento (control de fuga de datos). */
  n_ids_entrenamiento: number;
  valida_para_comparacion: boolean;
  motivo_invalidez: string;
  activo: boolean;
}

/** Eficiencia medida del modelo (tabla `modelos.eficiencia`, Fase A3). */
export interface EficienciaModelo {
  tiempo_entrenamiento_s?: number;
  tamano_modelo_kb?: number;
  fecha_medicion?: string;
  n_predicciones?: number;
  n_textos_distintos?: number;
  latencia_media_ms?: number | null;
  latencia_p95_ms?: number | null;
}

/** Métricas de un algoritmo en la comparación de la validación cruzada. */
export interface MetricaAlgoritmo {
  f1_macro: number;
  accuracy: number;
  precision_macro: number;
  recall_macro: number;
}

/** Hiperparámetros reales extraídos del binario de un clasificador. */
export interface HiperparametrosClasificador {
  C: number | null;
  alpha: number | null;
  class_weight: string | null;
  max_iter: number | null;
  calibrado: boolean;
}

/** Parámetros completos del modelo activo (endpoint /api/modelo/parametros, A2). */
export interface ParametrosModelo {
  version: string;
  fecha: string;
  algoritmo_categoria: string;
  algoritmo_prioridad: string;
  hiperparametros: {
    vectorizador: Record<string, unknown>;
    categoria: HiperparametrosClasificador;
    prioridad: HiperparametrosClasificador;
  };
  tfidf: {
    n_caracteristicas: number;
    tamano_vocabulario: number;
    ngram_range: [number, number];
    min_df: number;
    sublinear_tf: boolean;
    n_caracteristicas_prioridad: number;
  };
  division: {
    esquema: string;
    semilla: number;
    entrenamiento: number;
    prueba_fija: number;
    prueba_externa: number;
    proporcion_entrenamiento: number | null;
    proporcion_prueba: number | null;
    folds_max: number;
    validacion_cruzada: string;
  };
  umbrales: { confianza: number; margen: number };
  n_entrenamiento: number;
  n_prueba_fija: number;
  n_prueba_externa: number;
  version_prueba: string;
  metodo_evaluacion: string;
  comparacion_algoritmos: {
    ganador_categoria: string;
    ganador_prioridad: string;
    categoria: Record<string, MetricaAlgoritmo>;
    prioridad: Record<string, MetricaAlgoritmo>;
  };
  eficiencia: EficienciaModelo;
}

/** Metadatos de un informe del agente (tabla `informes`, Fase A5). */
export interface InformeResumen {
  id: number;
  fecha: string;
  version_modelo: string;
  generado_por: string;
  estado: string;
  error: string;
}

/** Informe completo del agente (Markdown + JSON estructurado). */
export interface Informe extends InformeResumen {
  contenido_md: string;
  contenido_json: Record<string, unknown>;
}

/** Respuesta al solicitar la generación de un informe. */
export interface InformeGenerarResponse {
  id: number;
  estado: string;
}

/** Estado de una generación de informe en segundo plano. */
export interface InformeEstado {
  id: number;
  estado: string;
  error: string;
}

/** Formato de descarga de un informe. */
export type FormatoInforme = "md" | "json" | "zip";

/** Respuesta del reentrenamiento. */
export interface EntrenarResponse {
  activado: boolean;
  motivo: string;
  version_nueva: Modelo | null;
  version_anterior: Modelo | null;
  comparacion_algoritmos: {
    categoria?: Record<string, { f1_macro: number; accuracy: number; precision_macro: number; recall_macro: number }>;
    prioridad?: Record<string, { f1_macro: number; accuracy: number; precision_macro: number; recall_macro: number }>;
    ganador_categoria?: string;
    ganador_prioridad?: string;
  };
  datos_suficientes: boolean;
  mensaje: string;
}

/** Progreso de etiquetado por categoría. */
export interface ProgresoCategoria {
  clave: string;
  nombre: string;
  etiquetadas: number;
  meta: number;
  faltan: number;
}

/** Estadísticas generales (endpoint /api/estadisticas). */
export interface Estadisticas {
  total_solicitudes: number;
  etiquetadas: number;
  sin_etiquetar: number;
  por_categoria: { clave: string; nombre: string; icono: string; total: number }[];
  por_etiquetador: { nombre: string; total: number }[];
  etiquetas_desde_ultimo_entrenamiento: number;
  version_activa: string | null;
  datos_suficientes: boolean;
  progreso_por_categoria: ProgresoCategoria[];
}

/** Cola priorizada de etiquetado (aprendizaje activo). */
export interface ColaEtiquetado {
  total_pendientes: number;
  meta_por_categoria: number;
  items: (Solicitud & { sugerencia_confirmar: string | null; margen: number | null })[];
}

/** Guía de criterios de etiquetado. */
export interface GuiaEtiquetado {
  prioridades: { nivel: Priority; criterio: string }[];
  desambiguaciones: { categoria: string; criterio: string }[];
  meta_por_categoria: number;
}

/** Resultado de la importación de un CSV. */
export interface ImportarResultado {
  total_filas: number;
  importadas: number;
  duplicadas: number;
  invalidas: { fila: number; id: string; motivo: string }[];
}

/** Estado real del servicio (endpoint /api/salud). */
export interface Salud {
  estado: string;
  servicio: string;
  base_datos: string;
  version_modelo: string | null;
  n_etiquetas: number;
  umbral_confianza: number;
  umbral_margen: number;
  api_key_activa: boolean;
}

/** Informe de calidad del dataset etiquetado (endpoint /api/calidad-dataset). */
export interface CalidadDataset {
  total: number;
  por_categoria: Record<string, number>;
  por_prioridad: Record<string, number>;
  desbalance: {
    maximo_por_clase?: number;
    minimo_por_clase?: number;
    razon_max_min?: number | null;
    coeficiente_variacion?: number;
  };
  longitud: {
    min_palabras?: number;
    max_palabras?: number;
    media_palabras?: number;
    mediana_palabras?: number;
  };
  duplicados_exactos: { grupos?: number; registros_extra?: number; ejemplos?: string[] };
  casi_duplicados: {
    umbral?: number;
    n_grupos?: number;
    registros_extra?: number;
    n_grupos_con_duplicados?: number;
    grupos?: { grupo: string; n: number; ejemplos: string[] }[];
  };
  etiquetas_contradictorias: {
    n?: number;
    ejemplos?: { texto: string; etiquetas: { categoria: string; prioridad: string }[] }[];
  };
  vocabulario_unico: number;
}

/** Acuerdo entre etiquetadores (kappa de Cohen) — endpoint /api/acuerdo-etiquetadores. */
export interface AcuerdoEtiquetadores {
  kappa_categoria: number | null;
  kappa_prioridad: number | null;
  puntuacion_observada_categoria: number | null;
  puntuacion_observada_prioridad: number | null;
  n_solicitudes_dobles: number;
  n_etiquetadores: number;
  discrepancias: {
    solicitud_id: number;
    texto: string;
    etiquetas: { etiquetador: string; categoria: string; prioridad: string }[];
  }[];
  mensaje: string;
}

/** Punto de la curva "a más etiquetas, mejor agente" (tabla `experimentos`). */
export interface PuntoMejora {
  fraccion: number;
  n_entrenamiento: number;
  accuracy_media: number;
  accuracy_sd: number;
  f1_media: number;
  f1_sd: number;
  repeticiones: number;
}

/** Experimento guardado en la tabla `experimentos`. */
export interface ExperimentoMejora {
  id: number;
  fecha: string;
  tipo: string;
  n_total: number;
  resultado: {
    puntos?: PuntoMejora[];
    algoritmo?: string;
    n_prueba?: number;
    n_pool?: number;
    semillas?: number[];
    metodologia?: string;
  };
}

/** Secciones del panel administrativo. */
export type AdminSection =
  | "overview"
  | "requests"
  | "etiquetado"
  | "map"
  | "crews"
  | "prueba"
  | "model";
