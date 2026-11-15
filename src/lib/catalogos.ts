/**
 * Catálogos estáticos de apoyo (configuración operativa del municipio).
 *
 * No son métricas ni resultados del modelo: son listas de referencia que usa la
 * interfaz (OTB disponibles, cuadrillas registradas). Todos los datos del sistema
 * —solicitudes, predicciones y métricas— provienen de la API y de la base de datos.
 */

import type { IconName } from "@/types";

/** OTB disponibles en el kiosco con su zona. */
export interface OtbOpcion {
  name: string;
  zone: string;
  district: string;
}

export const OTB_OPTIONS: OtbOpcion[] = [
  { name: "OTB Villa Esperanza", zone: "Distrito 3 · Zona Norte", district: "Distrito 3" },
  { name: "OTB Alto Cochabamba", zone: "Distrito 2 · Zona Sur", district: "Distrito 2" },
  { name: "OTB Central Norte", zone: "Distrito 11 · Centro", district: "Distrito 11" },
  { name: "OTB Barrio Bolívar", zone: "Distrito 5 · Zona Este", district: "Distrito 5" },
  { name: "OTB Nueva Vida", zone: "Distrito 7 · Zona Oeste", district: "Distrito 7" },
  { name: "OTB San Miguel", zone: "Distrito 9 · Zona Sudeste", district: "Distrito 9" },
  { name: "OTB Ceibo", zone: "Distrito 4 · Zona Sur", district: "Distrito 4" },
  { name: "OTB San Martín", zone: "Distrito 1 · Zona Norte", district: "Distrito 1" },
  { name: "OTB Los Pinos", zone: "Distrito 6 · Zona Oeste", district: "Distrito 6" },
  { name: "OTB El Mirador", zone: "Distrito 8 · Zona Este", district: "Distrito 8" },
  { name: "OTB La Recoleta", zone: "Distrito 10 · Centro", district: "Distrito 10" },
  { name: "OTB Tiquipaya", zone: "Distrito 12 · Zona Norte", district: "Distrito 12" },
];

/**
 * Extrae una OTB del texto libre (por ejemplo, del dictado por voz).
 *
 * Estrategia:
 *   1. Busca el patrón "OTB <nombre>" en el texto (la forma más fiable).
 *   2. Si no lo encuentra, hace matching por palabras clave del nombre,
 *      ignorando "OTB", "Villa", "Barrio", tildes y mayúsculas.
 *
 * Devuelve el nombre de la OTB encontrada o cadena vacía si no hay coincidencia.
 */
export function extraerOtb(texto: string): string {
  const limpio = texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");

  // 1) Patrón "OTB <nombre>": captura una o dos palabras después de "OTB".
  const patronOtb = /\botb\s+([a-záéíóúüñ]+(?:\s+[a-záéíóúüñ]+)?)/;
  const match = limpio.match(patronOtb);
  if (match) {
    const mencion = match[1].trim();
    // Busca la OTB cuyo nombre contenga la mención capturada.
    const directa = OTB_OPTIONS.find((opcion) => {
      const nombreLimpio = opcion.name
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
      return nombreLimpio.includes(mencion) || mencion.includes(nombreLimpio.split(/\s+/).filter(Boolean).slice(1).join(" "));
    });
    if (directa) return directa.name;

    // Si no hubo coincidencia exacta, busca por la primera palabra capturada.
    const primeraPalabra = mencion.split(/\s+/)[0];
    if (primeraPalabra && primeraPalabra.length >= 4) {
      const porPalabra = OTB_OPTIONS.find((opcion) => {
        const palabras = opcion.name
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .split(/\s+/)
          .filter((p) => p !== "otb");
        return palabras.some((p) => p === primeraPalabra || p.includes(primeraPalabra));
      });
      if (porPalabra) return porPalabra.name;
    }
  }

  // 2) Matching por palabras clave (sin el prefijo "OTB").
  const ruido = new Set([
    "otb",
    "villa",
    "barrio",
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "en",
    "zona",
    "distrito",
  ]);

  let mejorCoincidencia = "";
  let mejorPuntaje = 0;

  for (const opcion of OTB_OPTIONS) {
    const palabras = opcion.name
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .split(/\s+/)
      .filter((p) => !ruido.has(p));

    let puntaje = 0;
    for (const palabra of palabras) {
      if (palabra.length < 4) continue;
      if (limpio.includes(palabra)) puntaje += palabra.length;
    }

    if (puntaje > mejorPuntaje) {
      mejorPuntaje = puntaje;
      mejorCoincidencia = opcion.name;
    }
  }

  // Se exige un puntaje mínimo para evitar falsos positivos.
  return mejorPuntaje >= 6 ? mejorCoincidencia : "";
}

/** Cuadrillas operativas del municipio (catálogo de referencia). */
export interface Cuadrilla {
  id: string;
  name: string;
  specialty: string;
  status: "Disponible" | "En ruta" | "En operación";
  load: string;
  base: string;
  categoria: string;
  icon: IconName;
}

export const CREWS: Cuadrilla[] = [
  { id: "HIDRO-03", name: "HIDRO-03", specialty: "Agua y saneamiento", status: "En ruta", load: "5/6", base: "Villa Esperanza", categoria: "agua", icon: "droplet" },
  { id: "PLUVIAL-01", name: "PLUVIAL-01", specialty: "Drenaje pluvial", status: "Disponible", load: "2/5", base: "Central Norte", categoria: "drenaje", icon: "waves" },
  { id: "VIAL-07", name: "VIAL-07", specialty: "Infraestructura vial", status: "Disponible", load: "3/5", base: "Alto Cochabamba", categoria: "calles", icon: "road" },
  { id: "LUZ-04", name: "LUZ-04", specialty: "Alumbrado público", status: "En operación", load: "4/4", base: "Central Norte", categoria: "alumbrado", icon: "lightbulb" },
  { id: "ASEO-12", name: "ASEO-12", specialty: "Aseo urbano", status: "Disponible", load: "2/6", base: "Barrio Bolívar", categoria: "limpieza", icon: "trash" },
  { id: "VERDE-02", name: "VERDE-02", specialty: "Áreas verdes", status: "Disponible", load: "2/4", base: "Nueva Vida", categoria: "areas_verdes", icon: "leaf" },
  { id: "SEG-09", name: "SEG-09", specialty: "Seguridad ciudadana", status: "En ruta", load: "6/6", base: "San Miguel", categoria: "seguridad", icon: "shield" },
  { id: "AMBIENTE-05", name: "AMBIENTE-05", specialty: "Control ambiental", status: "Disponible", load: "1/4", base: "Villa Esperanza", categoria: "contaminacion", icon: "factory" },
];

/** Formatea una fecha ISO como antigüedad legible (por ejemplo "Hace 5 min"). */
export function relativeTime(fechaISO: string): string {
  const fecha = new Date(fechaISO).getTime();
  if (!Number.isFinite(fecha)) return "—";
  const minutos = Math.max(0, Math.round((Date.now() - fecha) / 60_000));
  if (minutos < 1) return "Hace instantes";
  if (minutos < 60) return `Hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `Hace ${horas} h`;
  const dias = Math.round(horas / 24);
  return `Hace ${dias} d`;
}

/** Devuelve la cuadrilla sugerida para una categoría. */
export function crewForCategory(clave: string): Cuadrilla | undefined {
  return CREWS.find((crew) => crew.categoria === clave);
}
