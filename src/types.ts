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

export type RequestOrigin = "kiosco" | "importado" | "panel";

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
  prediccion_detalle?: Prediccion | null;
  etiquetada: boolean;
  etiqueta: Etiqueta | null;
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
}

/** Métricas por clase del modelo. */
export interface MetricaClase {
  precision: number;
  recall: number;
  f1: number;
  soporte: number;
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
  activo: boolean;
}

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

/** Secciones del panel administrativo. */
export type AdminSection = "overview" | "requests" | "etiquetado" | "map" | "crews" | "model";
