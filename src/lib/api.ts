/**
 * Cliente de la API del Kiosco Ciudadano.
 *
 * El frontend NUNCA se conecta a la base de datos: todas las operaciones pasan
 * por el backend de FastAPI. En desarrollo, Vite redirige `/api` a
 * `http://127.0.0.1:8000` mediante un proxy (ver vite.config.ts).
 */

import type {
  AcuerdoEtiquetadores,
  CalidadDataset,
  Categoria,
  ColaEtiquetado,
  EntrenarResponse,
  Estadisticas,
  ExperimentoMejora,
  FormatoInforme,
  GuiaEtiquetado,
  ImportarResultado,
  Informe,
  InformeEstado,
  InformeGenerarResponse,
  InformeResumen,
  Modelo,
  ParametrosModelo,
  Prediccion,
  Priority,
  RequestOrigin,
  RequestStatus,
  Salud,
  Solicitud,
} from "@/types";

/** Ruta base de la API (el proxy de Vite la redirige al backend). */
const BASE = "/api";

/**
 * Clave de API del frontend (opcional). Si el backend tiene configurada
 * `API_KEY`, hay que definir `VITE_API_KEY` con el mismo valor para poder usar
 * los endpoints sensibles (entrenar, activar, importar y etiquetar).
 */
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

/** Cabeceras base de cada petición (incluye la clave de API si está definida). */
function cabecerasBase(extra?: HeadersInit): Record<string, string> {
  const cabeceras: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) cabeceras["X-API-Key"] = API_KEY;
  if (!extra) return cabeceras;
  if (extra instanceof Headers) {
    extra.forEach((valor, clave) => {
      cabeceras[clave] = valor;
    });
  } else if (Array.isArray(extra)) {
    extra.forEach(([clave, valor]) => {
      cabeceras[clave] = valor;
    });
  } else {
    Object.assign(cabeceras, extra);
  }
  return cabeceras;
}

/** Error de la API con el mensaje devuelto por el backend. */
export class ApiError extends Error {
  status: number;

  constructor(mensaje: string, status: number) {
    super(mensaje);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Realiza una petición HTTP con tiempo máximo y deserializa la respuesta JSON. */
async function pedir<T>(
  ruta: string,
  opciones: RequestInit = {},
  tiempoMaximoMs = 20_000,
): Promise<T> {
  const controlador = new AbortController();
  const cancelarPorUsuario = () => controlador.abort();
  opciones.signal?.addEventListener("abort", cancelarPorUsuario, { once: true });
  const temporizador = window.setTimeout(() => controlador.abort(), tiempoMaximoMs);

  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      ...opciones,
      signal: controlador.signal,
      headers: cabecerasBase(opciones.headers),
    });
  } catch (fallo) {
    if (opciones.signal?.aborted) throw fallo;
    if (controlador.signal.aborted) {
      throw new ApiError("La petición tardó demasiado. Comprueba la API e inténtalo de nuevo.", 408);
    }
    throw new ApiError(
      "No se pudo conectar con el servidor. Verifica que la API esté en ejecución (npm run api).",
      0,
    );
  } finally {
    window.clearTimeout(temporizador);
    opciones.signal?.removeEventListener("abort", cancelarPorUsuario);
  }

  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = (await respuesta.json()) as { detail?: string };
      if (cuerpo?.detail) detalle = cuerpo.detail;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    // Errores del proxy de Vite (502) o del servidor (5xx) suelen deberse a que
    // el backend no está corriendo.
    if (respuesta.status >= 500) {
      detalle =
        "El servidor de inteligencia artificial no está disponible. Asegúrate de iniciar la API con `npm run api`.";
    }
    throw new ApiError(detalle, respuesta.status);
  }

  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

// ---------------------------------------------------------------------------
// Categorías
// ---------------------------------------------------------------------------

/** Devuelve las 8 categorías municipales. */
export function listarCategorias(): Promise<Categoria[]> {
  return pedir<Categoria[]>("/categorias");
}

// ---------------------------------------------------------------------------
// Solicitudes
// ---------------------------------------------------------------------------

/** Crea una solicitud en el kiosco; el backend la clasifica y la guarda. */
export function crearSolicitud(payload: {
  texto: string;
  otb: string;
  zona?: string;
  origen?: RequestOrigin;
}): Promise<Solicitud> {
  return pedir<Solicitud>("/solicitudes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Lista solicitudes con filtros opcionales. */
export function listarSolicitudes(filtros: {
  estado?: RequestStatus;
  categoria?: string;
  etiquetada?: boolean;
  confianza_max?: number;
  origen?: RequestOrigin;
  texto?: string;
  limite?: number;
} = {}): Promise<Solicitud[]> {
  const parametros = new URLSearchParams();
  Object.entries(filtros).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== "") {
      parametros.append(clave, String(valor));
    }
  });
  const consulta = parametros.toString();
  return pedir<Solicitud[]>(`/solicitudes${consulta ? `?${consulta}` : ""}`);
}

/** Cambia el estado operativo de una solicitud. */
export function cambiarEstado(id: number, estado: RequestStatus): Promise<Solicitud> {
  return pedir<Solicitud>(`/solicitudes/${id}/estado`, {
    method: "PATCH",
    body: JSON.stringify({ estado }),
  });
}

/** Asigna una solicitud a una cuadrilla. */
export function asignarSolicitud(id: number, cuadrilla: string): Promise<Solicitud> {
  return pedir<Solicitud>(`/solicitudes/${id}/asignar`, {
    method: "PATCH",
    body: JSON.stringify({ cuadrilla }),
  });
}

/** Registra la etiqueta correcta de una solicitud (categoría y prioridad). */
export function etiquetarSolicitud(
  id: number,
  payload: { categoria_clave: string; prioridad: Priority; etiquetado_por: string },
): Promise<Solicitud> {
  return pedir<Solicitud>(`/solicitudes/${id}/etiqueta`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Importa etiquetas desde un CSV (columnas: ID, Solicitud, Categoría, Prioridad). */
export function importarCsv(csv: string): Promise<ImportarResultado> {
  return pedir<ImportarResultado>("/solicitudes/importar", {
    method: "POST",
    headers: { "Content-Type": "text/csv" },
    body: csv,
  });
}

// ---------------------------------------------------------------------------
// Etiquetado (aprendizaje activo)
// ---------------------------------------------------------------------------

/** Guía de criterios de etiquetado. */
export function obtenerGuia(): Promise<GuiaEtiquetado> {
  return pedir<GuiaEtiquetado>("/etiquetado/guia");
}

/** Cola priorizada de solicitudes por etiquetar. */
export function obtenerCola(limite = 25): Promise<ColaEtiquetado> {
  return pedir<ColaEtiquetado>(`/etiquetado/cola?limite=${limite}`);
}

// ---------------------------------------------------------------------------
// Modelo
// ---------------------------------------------------------------------------

/** Ejecuta el reentrenamiento del agente. */
export function entrenarModelo(forzar = false): Promise<EntrenarResponse> {
  return pedir<EntrenarResponse>("/modelo/entrenar", {
    method: "POST",
    body: JSON.stringify({ forzar }),
  }, 180_000);
}

/** Versión activa del modelo (o null si aún no hay ninguna). */
export function modeloActivo(): Promise<Modelo | null> {
  return pedir<Modelo | null>("/modelo/activo");
}

/** Todas las versiones entrenadas. */
export function listarVersiones(): Promise<Modelo[]> {
  return pedir<Modelo[]>("/modelo/versiones");
}

/** Activa una versión concreta (rollback). `forzar` permite activar versiones no comparables. */
export function activarVersion(version: string, forzar = false): Promise<Modelo> {
  const sufijo = forzar ? "?forzar=true" : "";
  return pedir<Modelo>(`/modelo/${version}/activar${sufijo}`, { method: "POST" });
}

/** Parámetros completos del modelo activo (Fase A2 + eficiencia A3). */
export function modeloParametros(): Promise<ParametrosModelo> {
  return pedir<ParametrosModelo>("/modelo/parametros");
}

// ---------------------------------------------------------------------------
// Informe del agente (Fase A5)
// ---------------------------------------------------------------------------

/** Genera y guarda un informe del agente (Markdown + JSON). */
export function generarInforme(payload: {
  textos_ejemplo?: string[];
  generado_por?: string;
  segundo_plano?: boolean;
}): Promise<InformeGenerarResponse> {
  return pedir<InformeGenerarResponse>(
    "/informe/generar",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

/** Historial de informes generados, del más reciente al más antiguo. */
export function listarInformes(): Promise<InformeResumen[]> {
  return pedir<InformeResumen[]>("/informe");
}

/** Contenido completo de un informe (Markdown + JSON estructurado). */
export function obtenerInforme(id: number): Promise<Informe> {
  return pedir<Informe>(`/informe/${id}`);
}

/** Estado de una generación de informe en segundo plano. */
export function estadoInforme(id: number): Promise<InformeEstado> {
  return pedir<InformeEstado>(`/informe/${id}/estado`);
}

/**
 * Descarga el informe en el formato indicado y devuelve el contenido como Blob.
 *
 * Se usa `fetch` (en lugar de un enlace directo) porque el endpoint exige la
 * cabecera `X-API-Key` cuando el backend tiene la clave configurada.
 */
export async function descargarInforme(id: number, formato: FormatoInforme): Promise<Blob> {
  const respuesta = await fetch(`${BASE}/informe/${id}/descargar?formato=${formato}`, {
    headers: cabecerasBase(),
  });
  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = (await respuesta.json()) as { detail?: string };
      if (cuerpo?.detail) detalle = cuerpo.detail;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new ApiError(detalle, respuesta.status);
  }
  return respuesta.blob();
}

// ---------------------------------------------------------------------------
// Estadísticas y predicción
// ---------------------------------------------------------------------------

/** Estadísticas reales del dataset y del etiquetado. */
export function obtenerEstadisticas(): Promise<Estadisticas> {
  return pedir<Estadisticas>("/estadisticas");
}

/** Predice sin guardar (inspector NLP y vista previa del kiosco). */
export function predecir(texto: string, signal?: AbortSignal): Promise<Prediccion> {
  return pedir<Prediccion>("/predecir", {
    method: "POST",
    body: JSON.stringify({ texto }),
    signal,
  });
}

// ---------------------------------------------------------------------------
// Sistema: salud, calidad del dataset, acuerdo y experimentos
// ---------------------------------------------------------------------------

/** Estado REAL del servicio (base de datos, modelo activo y umbrales). */
export function obtenerSalud(): Promise<Salud> {
  return pedir<Salud>("/salud");
}

/** Informe de calidad del dataset etiquetado. */
export function obtenerCalidadDataset(): Promise<CalidadDataset> {
  return pedir<CalidadDataset>("/calidad-dataset", {}, 60_000);
}

/** Acuerdo entre etiquetadores (kappa de Cohen) y discrepancias. */
export function obtenerAcuerdo(): Promise<AcuerdoEtiquetadores> {
  return pedir<AcuerdoEtiquetadores>("/acuerdo-etiquetadores");
}

/** Experimentos guardados (p. ej. la demostración de mejora por volumen). */
export function listarExperimentos(): Promise<ExperimentoMejora[]> {
  return pedir<ExperimentoMejora[]>("/experimentos");
}
