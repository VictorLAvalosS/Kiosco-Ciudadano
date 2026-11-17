import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type {
  AcuerdoEtiquetadores,
  CalidadDataset,
  Categoria,
  EntrenarResponse,
  Estadisticas,
  ExperimentoMejora,
  GuiaEtiquetado,
  IconName,
  Modelo,
  ParametrosModelo,
} from "@/types";
import {
  activarVersion,
  entrenarModelo,
  listarCategorias,
  listarExperimentos,
  listarVersiones,
  modeloActivo,
  modeloParametros,
  obtenerAcuerdo,
  obtenerCalidadDataset,
  obtenerEstadisticas,
  obtenerGuia,
} from "@/lib/api";
import { Icon } from "@/components/Icon";
import { EcuacionLista } from "@/components/Ecuacion";
import { InformeCard } from "@/components/InformeCard";

/** Abreviaturas usadas en la matriz de confusión (encabezados de 8 columnas). */
const ABREVIATURA: Record<string, string> = {
  alumbrado: "Alum",
  limpieza: "Limp",
  calles: "Call",
  agua: "Agua",
  seguridad: "Seg",
  areas_verdes: "Verde",
  drenaje: "Dren",
  contaminacion: "Amb",
};

const COLORES_VERSION = ["#00d9ff", "#5b8cff", "#805cff", "#19ce9a", "#f3b43f", "#ff7a59"];

/** Formatea cualquier valor de los parámetros del modelo (booleano, lista o nulo). */
function formatearParametro(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  if (typeof valor === "boolean") return valor ? "sí" : "no";
  if (Array.isArray(valor)) return `[${valor.join(", ")}]`;
  if (typeof valor === "object") return JSON.stringify(valor);
  return String(valor);
}

/** Formatea un número medido (tiempo, tamaño o latencia) con su unidad. */
function formatearNumero(valor: number | null | undefined, unidad = "", decimales = 2): string {
  if (valor === null || valor === undefined) return "—";
  return `${valor.toFixed(decimales)}${unidad}`;
}

/** Fila «etiqueta: valor» dentro de un bloque de parámetros del modelo. */
function ParametroFila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="parametro-fila">
      <span>{etiqueta}</span>
      <b>{valor}</b>
    </div>
  );
}

/** Etapas del ciclo de mejora continua del agente (Fase B4). */
const CICLO_MEJORA: { numero: number; titulo: string; detalle: string; descripcion: string }[] = [
  {
    numero: 1,
    titulo: "Etiquetar",
    detalle: "Dato supervisado",
    descripcion:
      "El equipo clasifica solicitudes reales (categoría y prioridad) y las guarda en Supabase.",
  },
  {
    numero: 2,
    titulo: "Reentrenar",
    detalle: "TF-IDF + algoritmo",
    descripcion:
      "El vectorizador y el clasificador se reajustan con el corpus etiquetado actualizado.",
  },
  {
    numero: 3,
    titulo: "Evaluar",
    detalle: "Prueba fija + externa",
    descripcion:
      "Se mide el F1 macro y se verifica que no haya fuga de datos entre train y prueba.",
  },
  {
    numero: 4,
    titulo: "Decidir",
    detalle: "Solo si mejora",
    descripcion:
      "La versión se activa únicamente si es comparable y supera a la que está en uso.",
  },
  {
    numero: 5,
    titulo: "Operar",
    detalle: "Umbrales (Ec.9)",
    descripcion:
      "El agente clasifica solicitudes y deriva a revisión humana los casos dudosos.",
  },
  {
    numero: 6,
    titulo: "Aprender",
    detalle: "Nuevas etiquetas",
    descripcion:
      "Las revisiones humanas aportan nuevas etiquetas y el ciclo vuelve a empezar.",
  },
];

/** Gráfico de línea para la curva de aprendizaje (F1 macro según el tamaño de datos). */
function CurvaAprendizaje({
  tamanos,
  validacion,
  entrenamiento,
}: {
  tamanos: number[];
  validacion: number[];
  entrenamiento: number[];
}) {
  if (tamanos.length < 2) {
    return (
      <p className="zone-empty">
        No hay suficientes datos para trazar la curva de aprendizaje todavía.
      </p>
    );
  }

  const ancho = 340;
  const alto = 130;
  const margen = 18;

  const punto = (indice: number, valor: number) => {
    const x = margen + (indice / (tamanos.length - 1)) * (ancho - margen * 2);
    const y = alto - margen - valor * (alto - margen * 2);
    return [x, y] as const;
  };

  const ruta = (valores: number[]) =>
    valores
      .map((valor, indice) => {
        const [x, y] = punto(indice, valor);
        return `${indice === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <div className="learning-curve">
      <svg viewBox={`0 0 ${ancho} ${alto}`} preserveAspectRatio="none">
        {[0, 0.25, 0.5, 0.75, 1].map((nivel) => {
          const [, y] = punto(0, nivel);
          return (
            <line
              key={nivel}
              x1={margen}
              x2={ancho - margen}
              y1={y}
              y2={y}
              stroke="rgba(130,206,220,0.16)"
              strokeWidth="1"
            />
          );
        })}
        <path d={ruta(entrenamiento)} fill="none" stroke="#805cff" strokeWidth="2" />
        <path d={ruta(validacion)} fill="none" stroke="#00d9ff" strokeWidth="2" />
        {validacion.map((valor, indice) => {
          const [x, y] = punto(indice, valor);
          return <circle key={indice} cx={x} cy={y} r="2.5" fill="#00d9ff" />;
        })}
      </svg>
      <div className="curve-axis">
        {tamanos.map((valor) => (
          <span key={valor}>{valor}</span>
        ))}
      </div>
      <div className="curve-legend">
        <span>
          <i style={{ background: "#00d9ff" }} /> F1 de validación
        </span>
        <span>
          <i style={{ background: "#805cff" }} /> F1 de entrenamiento
        </span>
        <em>eje X: nº de ejemplos · eje Y: F1 macro</em>
      </div>
    </div>
  );
}

/** Gráfico de evolución del F1 macro y accuracy a lo largo de las versiones. */
function EvolucionVersiones({ versiones }: { versiones: Modelo[] }) {
  // Solo se muestran las versiones comparables (entrenadas sin el conjunto de prueba).
  const ordenadas = [...versiones]
    .filter((modelo) => modelo.valida_para_comparacion !== false)
    .reverse();
  if (ordenadas.length < 2) {
    return (
      <p className="zone-empty">
        Se necesita más de una versión comparable para mostrar la evolución. Reentrena el
        agente tras etiquetar nuevas solicitudes.
      </p>
    );
  }
  return (
    <div className="version-evolution">
      {ordenadas.map((modelo, indice) => {
        const altura = Math.max(4, modelo.f1_macro * 100);
        const etiquetas = modelo.evaluacion?.n_etiquetas ?? modelo.n_entrenamiento;
        return (
          <div className={modelo.activo ? "active" : ""} key={modelo.version}>
            <i style={{ height: `${altura}%`, background: COLORES_VERSION[indice % 6] }} />
            <b>{(modelo.f1_macro * 100).toFixed(1)}%</b>
            <span>{modelo.version}</span>
            <small>acc {(modelo.accuracy * 100).toFixed(1)}%</small>
            <small>{etiquetas} etiquetas</small>
          </div>
        );
      })}
    </div>
  );
}

/** Curva cobertura-precisión: elección justificada del umbral de revisión. */
function CurvaCobertura({
  puntos,
  umbral,
}: {
  puntos: { umbral: number; n: number; cobertura: number; precision: number | null }[];
  umbral?: number;
}) {
  if (puntos.length < 2) {
    return <p className="zone-empty">Sin curva de cobertura disponible para esta versión.</p>;
  }
  const ancho = 340;
  const alto = 130;
  const margen = 20;
  const punto = (cobertura: number, precision: number) => {
    const x = margen + cobertura * (ancho - margen * 2);
    const y = alto - margen - precision * (alto - margen * 2);
    return `${x.toFixed(1)} ${y.toFixed(1)}`;
  };
  const ruta = puntos
    .filter((p) => p.precision !== null)
    .map((p, i) => `${i === 0 ? "M" : "L"}${punto(p.cobertura, p.precision ?? 0)}`)
    .join(" ");
  const actual = umbral !== undefined ? puntos.reduce(
    (mejor, p) => (Math.abs(p.umbral - umbral) < Math.abs(mejor.umbral - umbral) ? p : mejor),
    puntos[0],
  ) : null;

  return (
    <div className="learning-curve">
      <svg viewBox={`0 0 ${ancho} ${alto}`} preserveAspectRatio="none">
        {[0, 0.25, 0.5, 0.75, 1].map((nivel) => {
          const y = alto - margen - nivel * (alto - margen * 2);
          return (
            <line
              key={nivel}
              x1={margen}
              x2={ancho - margen}
              y1={y}
              y2={y}
              stroke="rgba(130,206,220,0.16)"
              strokeWidth="1"
            />
          );
        })}
        <path d={ruta} fill="none" stroke="#19ce9a" strokeWidth="2" />
        {puntos
          .filter((p) => p.precision !== null)
          .map((p) => {
            const [x, y] = punto(p.cobertura, p.precision ?? 0).split(" ");
            return (
              <circle
                key={p.umbral}
                cx={x}
                cy={y}
                r={actual && p.umbral === actual.umbral ? 4 : 2.5}
                fill={actual && p.umbral === actual.umbral ? "#f3b43f" : "#19ce9a"}
              />
            );
          })}
      </svg>
      <div className="curve-legend">
        <span>
          <i style={{ background: "#19ce9a" }} /> Precisión frente a cobertura
        </span>
        {actual && (
          <span>
            <i style={{ background: "#f3b43f" }} /> Umbral en uso ({actual.umbral})
          </span>
        )}
        <em>eje X: cobertura (casos aceptados) · eje Y: precisión</em>
      </div>
    </div>
  );
}

/** Barras de la mejora por volumen de etiquetas (media ± desviación estándar). */
function GraficoMejora({ puntos }: { puntos: ExperimentoMejora["resultado"]["puntos"] }) {
  if (!puntos || puntos.length === 0) {
    return (
      <p className="zone-empty">
        Aún no se ha ejecutado la demostración de mejora. Ejecuta{" "}
        <b>python demo_mejora.py</b> en el backend.
      </p>
    );
  }
  return (
    <div className="version-evolution">
      {puntos.map((punto, indice) => (
        <div key={punto.fraccion}>
          <i
            style={{
              height: `${Math.max(4, punto.f1_media * 100)}%`,
              background: COLORES_VERSION[indice % 6],
            }}
          />
          <b>{(punto.f1_media * 100).toFixed(1)}%</b>
          <span>{Math.round(punto.fraccion * 100)}%</span>
          <small>{punto.n_entrenamiento} casos</small>
          <small>± {(punto.f1_sd * 100).toFixed(1)}</small>
        </div>
      ))}
    </div>
  );
}

/**
 * Mapa de calor de una matriz de confusión (categoría 8×8 o prioridad 3×3).
 *
 * Permite alternar entre los valores ABSOLUTOS (nº de casos) y los NORMALIZADOS
 * por fila (proporción sobre el total real de cada clase). La intensidad del
 * color de cada celda es proporcional al valor; la diagonal se resalta.
 */
function MatrizConfusion({
  etiquetas,
  matriz,
  abreviatura,
  nombres,
  titulo,
}: {
  etiquetas: string[];
  matriz: number[][];
  abreviatura?: Record<string, string>;
  nombres?: Map<string, string>;
  titulo: string;
}) {
  const [modo, setModo] = useState<"absoluta" | "normalizada">("absoluta");
  const [ampliada, setAmpliada] = useState(false);
  const botonAmpliarRef = useRef<HTMLButtonElement>(null);
  const botonCerrarRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!ampliada) return;
    const anterior = document.body.style.overflow;
    const focoAnterior = document.activeElement;
    const cerrarConEscape = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") setAmpliada(false);
    };
    document.body.style.overflow = "hidden";
    botonCerrarRef.current?.focus();
    window.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.body.style.overflow = anterior;
      window.removeEventListener("keydown", cerrarConEscape);
      if (focoAnterior instanceof HTMLElement) focoAnterior.focus();
    };
  }, [ampliada]);

  if (etiquetas.length === 0 || matriz.length === 0) {
    return <p className="zone-empty">Sin matriz disponible para esta versión.</p>;
  }

  const corta = (clave: string, completa = false) =>
    completa
      ? (nombres?.get(clave) ?? clave.replace(/_/g, " "))
      : (abreviatura?.[clave] ?? clave.slice(0, 5));

  // Normalización por fila: cada fila (clase real) suma 1.
  const normalizada = matriz.map((fila) => {
    const total = fila.reduce((suma, valor) => suma + valor, 0);
    return fila.map((valor) => (total > 0 ? valor / total : 0));
  });
  const valores = modo === "absoluta" ? matriz : normalizada;
  const maxAbsoluto = Math.max(1, ...matriz.flat());
  const intensidad = (i: number, j: number) =>
    modo === "absoluta" ? valores[i][j] / maxAbsoluto : valores[i][j];

  const contenido = (completa: boolean) => (
    <div className={`heatmap-wrap${completa ? " heatmap-expanded-content" : ""}`}>
      <div className="heatmap-toggle">
        <button
          aria-pressed={modo === "absoluta"}
          className={modo === "absoluta" ? "active" : ""}
          onClick={() => setModo("absoluta")}
          type="button"
        >
          ABSOLUTA
        </button>
        <button
          aria-pressed={modo === "normalizada"}
          className={modo === "normalizada" ? "active" : ""}
          onClick={() => setModo("normalizada")}
          type="button"
        >
          NORMALIZADA
        </button>
        <span>
          normalizada = proporción sobre el total real de cada clase (recall por fila)
        </span>
        {!completa && (
          <button
            className="heatmap-expand-button"
            onClick={() => setAmpliada(true)}
            ref={botonAmpliarRef}
            type="button"
          >
            AMPLIAR MATRIZ
          </button>
        )}
      </div>
      <div className="confusion-scroll">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th>Real ↓ / Predicción →</th>
              {etiquetas.map((clave) => (
                <th key={clave}>{corta(clave, completa)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matriz.map((_, i) => (
              <tr key={etiquetas[i] ?? i}>
                <th>{corta(etiquetas[i] ?? String(i), completa)}</th>
                {valores[i].map((valor, j) => {
                  const alfa = Math.min(0.85, Math.max(0, intensidad(i, j)));
                  return (
                    <td
                      className={i === j ? "diagonal" : ""}
                      key={j}
                      style={{
                        background:
                          alfa > 0
                            ? `rgba(0, 217, 255, ${0.06 + alfa * 0.5})`
                            : "transparent",
                      }}
                      title={`${etiquetas[i]} → ${etiquetas[j]}: ${
                        modo === "absoluta" ? matriz[i][j] : `${(valor * 100).toFixed(1)}%`
                      }`}
                    >
                      {modo === "absoluta" ? matriz[i][j] : `${(valor * 100).toFixed(0)}%`}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>La diagonal (celdas resaltadas) muestra las predicciones correctas.</p>
    </div>
  );

  return (
    <>
      {contenido(false)}
      {ampliada &&
        createPortal(
          <div
            className="heatmap-modal-backdrop"
            onMouseDown={(evento) => {
              if (evento.target === evento.currentTarget) setAmpliada(false);
            }}
          >
            <section
              aria-modal="true"
              aria-labelledby="heatmap-modal-title"
              className="heatmap-modal"
              role="dialog"
            >
              <header className="heatmap-modal-header">
                <div>
                  <span>MATRIZ DE CONFUSIÓN</span>
                  <h2 id="heatmap-modal-title">{titulo}</h2>
                </div>
                <button
                  aria-label="Cerrar matriz ampliada"
                  className="heatmap-modal-close"
                  onClick={() => setAmpliada(false)}
                  ref={botonCerrarRef}
                  type="button"
                >
                  CERRAR
                </button>
              </header>
              {contenido(true)}
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}

export function ModelPage({
  onNotice,
  onDemo,
}: {
  onNotice: (message: string) => void;
  onDemo?: () => void;
}) {
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [versiones, setVersiones] = useState<Modelo[]>([]);
  const [stats, setStats] = useState<Estadisticas | null>(null);
  const [guia, setGuia] = useState<GuiaEtiquetado | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [calidad, setCalidad] = useState<CalidadDataset | null>(null);
  const [acuerdo, setAcuerdo] = useState<AcuerdoEtiquetadores | null>(null);
  const [experimentos, setExperimentos] = useState<ExperimentoMejora[]>([]);
  const [parametros, setParametros] = useState<ParametrosModelo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [entrenando, setEntrenando] = useState(false);
  const [forzar, setForzar] = useState(false);
  const [resultado, setResultado] = useState<EntrenarResponse | null>(null);
  const [error, setError] = useState("");

  /** Recarga el modelo activo, el historial de versiones y las estadísticas. */
  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const [activo, historial, nuevasStats, nuevaGuia, nuevoCatalogo] = await Promise.all([
        modeloActivo(),
        listarVersiones(),
        obtenerEstadisticas(),
        obtenerGuia(),
        listarCategorias(),
      ]);
      setModelo(activo);
      setVersiones(historial);
      setStats(nuevasStats);
      setGuia(nuevaGuia);
      setCategorias(nuevoCatalogo);
      // Fuentes auxiliares de la defensa: calidad, acuerdo y mejora por volumen.
      // Se cargan por separado para que un fallo en una no bloquee el resto.
      void Promise.all([
        obtenerCalidadDataset().catch(() => null),
        obtenerAcuerdo().catch(() => null),
        listarExperimentos().catch(() => []),
        modeloParametros().catch(() => null),
      ]).then(([nuevaCalidad, nuevoAcuerdo, nuevosExperimentos, nuevosParametros]) => {
        setCalidad(nuevaCalidad);
        setAcuerdo(nuevoAcuerdo);
        setExperimentos(nuevosExperimentos);
        setParametros(nuevosParametros);
      });
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo consultar el modelo.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  /** Ejecuta el reentrenamiento real del agente. */
  const reentrenar = useCallback(async () => {
    setEntrenando(true);
    setError("");
    setResultado(null);
    try {
      const respuesta = await entrenarModelo(forzar);
      setResultado(respuesta);
      setModelo(respuesta.version_nueva ?? (await modeloActivo()));
      onNotice(
        respuesta.activado
          ? `Versión ${respuesta.version_nueva?.version ?? ""} entrenada y activada.`
          : "Se entrenó una versión nueva, pero no superó a la activa.",
      );
      await cargar();
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "El reentrenamiento falló.");
    } finally {
      setEntrenando(false);
    }
  }, [cargar, forzar, onNotice]);

  const activar = useCallback(
    async (version: string, forzar = false) => {
      try {
        await activarVersion(version, forzar);
        onNotice(
          forzar
            ? `Versión ${version} activada forzando una versión no comparable.`
            : `Versión ${version} activada (rollback).`,
        );
        await cargar();
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo activar la versión.");
      }
    },
    [cargar, onNotice],
  );

  const iconosPorClave = useMemo(
    () => new Map(categorias.map((c) => [c.clave, c.icono])),
    [categorias],
  );
  const nombresPorClave = useMemo(
    () => new Map(categorias.map((c) => [c.clave, c.nombre])),
    [categorias],
  );

  const matriz = modelo?.matriz_confusion ?? {};
  const etiquetasMatriz = matriz.etiquetas ?? [];
  const valoresMatriz = matriz.matriz ?? [];
  const totalCasos =
    (modelo?.n_entrenamiento ?? 0) + (modelo?.n_validacion ?? 0) + (modelo?.n_prueba ?? 0);
  const mayorParticion = Math.max(
    modelo?.n_entrenamiento ?? 0,
    modelo?.n_validacion ?? 0,
    modelo?.n_prueba ?? 0,
    1,
  );
  const pares = matriz.pares_confundidos ?? [];
  const porClase = modelo?.metricas_por_clase ?? {};
  const topTerminos: Record<string, { termino: string; peso: number }[]> =
    modelo?.top_terminos ?? {};
  // Lista [categoría, términos] tipada explícitamente (Object.entries sobre un
  // diccionario infiere mal el tipo del valor, por eso se fuerza aquí).
  const terminosPorCategoria = Object.entries(topTerminos.categoria ?? {}) as unknown as [
    string,
    { termino: string; peso: number }[],
  ][];
  const curva = modelo?.curva_aprendizaje ?? {};
  const comparacionCat =
    (modelo?.hiperparametros?.comparacion_categoria as
      | Record<string, { f1_macro: number; accuracy: number; precision_macro: number; recall_macro: number }>
      | undefined) ?? {};
  const comparacionPri =
    (modelo?.hiperparametros?.comparacion_prioridad as
      | Record<string, { f1_macro: number; accuracy: number; precision_macro: number; recall_macro: number }>
      | undefined) ?? {};

  // Evaluación ampliada (Fase 2): prioridad, baselines, calibración, errores y
  // confusión de prioridad, más el informe de calidad y el acuerdo entre etiquetadores.
  const evaluacion = modelo?.evaluacion ?? {};
  const matrizPri = evaluacion.matriz_confusion_prioridad ?? {};
  const etiquetasMatrizPri = matrizPri.etiquetas ?? [];
  const valoresMatrizPri = matrizPri.matriz ?? [];
  const paresPri = matrizPri.pares_confundidos ?? [];
  const porClasePri = evaluacion.metricas_por_clase_prioridad ?? {};
  const baselinesCat = (evaluacion.baselines_categoria ?? {}) as Record<
    string,
    { accuracy?: number; f1_macro?: number; clase?: string }
  >;
  const baselinesPri = (evaluacion.baselines_prioridad ?? {}) as Record<
    string,
    { accuracy?: number; f1_macro?: number; clase?: string }
  >;
  const calibracion = evaluacion.calibracion_categoria ?? {};
  const cobertura = evaluacion.curva_cobertura_precision ?? [];
  const errores = evaluacion.errores_categoria ?? [];
  const casiDuplicados = evaluacion.casi_duplicados ?? {};
  const umbralesRevision = evaluacion.umbrales_revision ?? {};
  // Métricas del conjunto de prueba EXTERNO (nunca usado al entrenar).
  const externo = evaluacion.prueba_externa ?? {};
  const mejoraPuntos = useMemo(
    () => experimentos.find((experimento) => experimento.tipo === "mejora_volumen"),
    [experimentos],
  );

  return (
    <section className="module-page model-page">
      <div className="module-heading">
        <div>
          <span>MODELO DE CLASIFICACIÓN CIUDADANA</span>
          <h2>Aprendizaje Supervisado + Procesamiento de Lenguaje Natural</h2>
          <p>Del texto libre del ciudadano a una categoría municipal verificable.</p>
        </div>
        <div className="heading-actions">
          <label className="force-toggle">
            <input type="checkbox" checked={forzar} onChange={(e) => setForzar(e.target.checked)} />
            Forzar activación
          </label>
          <button onClick={() => void reentrenar()} disabled={entrenando}>
            {entrenando ? "ENTRENANDO…" : "REENTRENAR AGENTE"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert-banner error">
          <Icon name="bolt" size={16} />
          <span>{error}</span>
        </div>
      )}

      {resultado && (
        <div className={`alert-banner ${resultado.activado ? "ok" : "warn"}`}>
          <Icon name={resultado.activado ? "check" : "bolt"} size={16} />
          <span>
            <b>{resultado.activado ? "Versión activada." : "Versión no activada."}</b>{" "}
            {resultado.motivo}
            {resultado.version_nueva && (
              <>
                {" "}
                Nueva versión <b>{resultado.version_nueva.version}</b> · F1 macro{" "}
                <b>{(resultado.version_nueva.f1_macro * 100).toFixed(1)}%</b>
                {resultado.version_anterior && (
                  <>
                    {" "}
                    vs. {resultado.version_anterior.version}{" "}
                    <b>{(resultado.version_anterior.f1_macro * 100).toFixed(1)}%</b>
                  </>
                )}
                . {resultado.mensaje}
              </>
            )}
          </span>
        </div>
      )}

      {stats && !stats.datos_suficientes && (
        <div className="alert-banner warn">
          <Icon name="bolt" size={16} />
          <span>
            <b>Datos insuficientes</b> (menos de 30 ejemplos por clase). El modelo se evalúa con
            validación cruzada y las métricas son preliminares. Meta: {guia?.meta_por_categoria ?? 50}{" "}
            etiquetas por categoría.
          </span>
        </div>
      )}

      <div className="academic-brief">
        <div className="brief-index">
          PROYECTO
          <br />
          <b>01</b>
        </div>
        <div>
          <small>ÁREA</small>
          <h3>Aprendizaje Supervisado</h3>
          <p>El modelo aprende con solicitudes previamente clasificadas por el equipo.</p>
        </div>
        <div>
          <small>SUBÁREA</small>
          <h3>Procesamiento de Lenguaje Natural</h3>
          <p>Comprende el texto, extrae términos relevantes y construye una representación numérica.</p>
        </div>
        <div>
          <small>PROBLEMA</small>
          <h3>Clasificación de solicitudes ciudadanas</h3>
          <p>Reduce la derivación manual y envía cada reclamo al área municipal correspondiente.</p>
        </div>
      </div>

      <div className="architecture-flow">
        {[
          "Texto ciudadano",
          "Normalización",
          "TF-IDF (1-2 gramas)",
          modelo?.algoritmo ?? "Clasificador supervisado",
          "Categoría + Prioridad",
        ].map((item, index) => (
          <div key={item}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <b>{item}</b>
            {index < 4 && <i>→</i>}
          </div>
        ))}
      </div>

      {cargando && <p className="zone-empty">Consultando el modelo almacenado en la base de datos…</p>}

      {!cargando && !modelo && (
        <div className="alert-banner warn">
          <Icon name="bolt" size={16} />
          <span>
            Todavía no existe ningún modelo entrenado. Importa etiquetas (o etiqueta en el módulo
            de Etiquetado) y pulsa <b>REENTRENAR AGENTE</b> para crear la primera versión.
          </span>
        </div>
      )}

      {modelo && (
        <>
          <div className="model-meta-bar">
            <span>
              VERSIÓN ACTIVA <b>{modelo.version}</b>
            </span>
            <span>
              ALGORITMO <b>{modelo.algoritmo}</b>
            </span>
            <span>
              EVALUACIÓN{" "}
              <b>
                {(modelo.hiperparametros?.metodo_evaluacion as string) === "conjunto_prueba_fijo"
                  ? "Conjunto de prueba fijo"
                  : "Validación cruzada"}
              </b>
            </span>
            <span>
              ENTRENADO{" "}
              <b>{new Date(modelo.fecha).toLocaleString("es-BO")}</b>
            </span>
          </div>

          <div className="model-detail-grid">
            <article>
              <small>CONJUNTO DE DATOS</small>
              <h3>
                {totalCasos} <span>casos etiquetados</span>
              </h3>
              <p>
                Solicitudes reales etiquetadas por el equipo y almacenadas en Supabase. El conjunto
                de prueba fijo nunca se usa para entrenar.
              </p>
              <div className="dataset-split">
                <span>
                  <i
                    style={{
                      width: `${(modelo.n_entrenamiento / mayorParticion) * 100}%`,
                    }}
                  />
                  {modelo.n_entrenamiento} Entrenamiento
                </span>
                <span>
                  <i
                    style={{
                      width: `${(modelo.n_validacion / mayorParticion) * 100}%`,
                    }}
                  />
                  {modelo.n_validacion} Validación
                </span>
                <span>
                  <i
                    style={{
                      width: `${(modelo.n_prueba / mayorParticion) * 100}%`,
                    }}
                  />
                  {modelo.n_prueba} Prueba fija
                </span>
              </div>
            </article>

            <article>
              <small>MÉTRICAS DE EVALUACIÓN</small>
              {[
                ["Accuracy", modelo.accuracy],
                ["Precision macro", modelo.precision_macro],
                ["Recall macro", modelo.recall_macro],
                ["F1 macro", modelo.f1_macro],
              ].map(([nombre, valor]) => {
                const numero = Number(valor) * 100;
                return (
                  <div className="metric-row" key={String(nombre)}>
                    <span>{nombre}</span>
                    <i>
                      <em style={{ width: `${numero}%` }} />
                    </i>
                    <b>{numero.toFixed(1)}%</b>
                  </div>
                );
              })}
            </article>
          </div>

          <div className="model-detail-grid">
            <article className="confusion-card">
              <small>MATRIZ DE CONFUSIÓN (CATEGORÍA)</small>
              <MatrizConfusion
                etiquetas={etiquetasMatriz}
                matriz={valoresMatriz}
                abreviatura={ABREVIATURA}
                nombres={nombresPorClave}
                titulo="Categoría"
              />
            </article>

            <article>
              <small>MÉTRICAS POR CATEGORÍA</small>
              <table className="class-metrics">
                <thead>
                  <tr>
                    <th>CATEGORÍA</th>
                    <th>P</th>
                    <th>R</th>
                    <th>F1</th>
                    <th>N</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(porClase).map(([clave, metrica]) => (
                    <tr key={clave}>
                      <td>
                        <Icon
                          name={(iconosPorClave.get(clave) ?? "bolt") as IconName}
                          size={13}
                        />{" "}
                        {nombresPorClave.get(clave) ?? clave}
                      </td>
                      <td>{(metrica.precision * 100).toFixed(1)}</td>
                      <td>{(metrica.recall * 100).toFixed(1)}</td>
                      <td>{(metrica.f1 * 100).toFixed(1)}</td>
                      <td>{metrica.soporte}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          </div>

          <div className="model-detail-grid">
            <article>
              <small>CURVA DE APRENDIZAJE</small>
              <CurvaAprendizaje
                tamanos={curva.tamanos ?? []}
                validacion={curva.f1_validacion ?? []}
                entrenamiento={curva.f1_entrenamiento ?? []}
              />
            </article>
            <article>
              <small>PARES DE CATEGORÍAS MÁS CONFUNDIDOS</small>
              {pares.length > 0 ? (
                <div className="lexicon-list">
                  {pares.map((par) => (
                    <div key={`${par.real}-${par.predicha}`}>
                      <span>
                        {ABREVIATURA[par.real] ?? par.real} → {ABREVIATURA[par.predicha] ?? par.predicha}
                      </span>
                      <b>{par.casos} casos</b>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="zone-empty">
                  No hay confusiones entre categorías en el conjunto de evaluación. Excelente
                  separación.
                </p>
              )}
            </article>
          </div>

          <div className="model-detail-grid">
            <article>
              <small>MÉTRICAS DEL CLASIFICADOR DE PRIORIDAD (ALTA / MEDIA / BAJA)</small>
              {[
                ["Accuracy", modelo.accuracy_prioridad],
                ["Precision macro", modelo.precision_prioridad],
                ["Recall macro", modelo.recall_prioridad],
                ["F1 macro", modelo.f1_prioridad],
              ].map(([nombre, valor]) => {
                const numero = Number(valor) * 100;
                return (
                  <div className="metric-row" key={String(nombre)}>
                    <span>{nombre}</span>
                    <i>
                      <em style={{ width: `${numero}%` }} />
                    </i>
                    <b>{numero.toFixed(1)}%</b>
                  </div>
                );
              })}
              <table className="class-metrics">
                <thead>
                  <tr>
                    <th>PRIORIDAD</th>
                    <th>P</th>
                    <th>R</th>
                    <th>F1</th>
                    <th>N</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(porClasePri).map(([clave, metrica]) => (
                    <tr key={clave}>
                      <td>{clave}</td>
                      <td>{(metrica.precision * 100).toFixed(1)}</td>
                      <td>{(metrica.recall * 100).toFixed(1)}</td>
                      <td>{(metrica.f1 * 100).toFixed(1)}</td>
                      <td>{metrica.soporte}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
            <article className="confusion-card">
              <small>MATRIZ DE CONFUSIÓN (PRIORIDAD)</small>
              <MatrizConfusion
                etiquetas={etiquetasMatrizPri}
                matriz={valoresMatrizPri}
                titulo="Prioridad"
              />
              {paresPri.length > 0 && (
                <p>
                  Confusión más frecuente: <b>{paresPri[0].real}</b> →{" "}
                  <b>{paresPri[0].predicha}</b> ({paresPri[0].casos} casos).
                </p>
              )}
            </article>
          </div>

          <div className="lexicon-grid">
            <article>
              <small>CONTRA BASELINES · CATEGORÍA</small>
              <table className="class-metrics">
                <thead>
                  <tr>
                    <th>MODELO</th>
                    <th>ACCURACY</th>
                    <th>F1 MACRO</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <b className="online-text">Agente (TF-IDF + {modelo.algoritmo})</b>
                    </td>
                    <td>{(modelo.accuracy * 100).toFixed(1)}</td>
                    <td>{(modelo.f1_macro * 100).toFixed(1)}</td>
                  </tr>
                  {["mayoritaria", "aleatoria_estratificada"].map((clave) => {
                    const base = baselinesCat[clave];
                    if (!base) return null;
                    return (
                      <tr key={clave}>
                        <td>
                          {clave === "mayoritaria"
                            ? `Clase mayoritaria${base.clase ? ` (${base.clase})` : ""}`
                            : "Aleatorio estratificado"}
                        </td>
                        <td>{((base.accuracy ?? 0) * 100).toFixed(1)}</td>
                        <td>{((base.f1_macro ?? 0) * 100).toFixed(1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p>
                El agente debe superar claramente al azar y a la clase mayoritaria; si no, no
                aporta valor frente a una regla trivial.
              </p>
            </article>
            <article>
              <small>CONTRA BASELINES · PRIORIDAD</small>
              <table className="class-metrics">
                <thead>
                  <tr>
                    <th>MODELO</th>
                    <th>ACCURACY</th>
                    <th>F1 MACRO</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <b className="online-text">Agente (prioridad)</b>
                    </td>
                    <td>{(modelo.accuracy_prioridad * 100).toFixed(1)}</td>
                    <td>{(modelo.f1_prioridad * 100).toFixed(1)}</td>
                  </tr>
                  {["mayoritaria", "aleatoria_estratificada"].map((clave) => {
                    const base = baselinesPri[clave];
                    if (!base) return null;
                    return (
                      <tr key={clave}>
                        <td>
                          {clave === "mayoritaria"
                            ? `Clase mayoritaria${base.clase ? ` (${base.clase})` : ""}`
                            : "Aleatorio estratificado"}
                        </td>
                        <td>{((base.accuracy ?? 0) * 100).toFixed(1)}</td>
                        <td>{((base.f1_macro ?? 0) * 100).toFixed(1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p>Permite comprobar cuánto aporta el modelo frente a predecir siempre la prioridad más común.</p>
            </article>
          </div>

          {externo.n ? (
            <div className="versions-card">
              <div className="section-title">
                <div>
                  <h3>CONJUNTO DE PRUEBA EXTERNO</h3>
                  <p>
                    Solicitudes nuevas (origen <b>prueba_externa</b>) que NUNCA se usaron para
                    entrenar. Miden la generalización del modelo frente al conjunto de prueba fijo.
                  </p>
                </div>
                <span className="stable">
                  <i /> {externo.n} casos externos
                </span>
              </div>
              <div className="lexicon-grid">
                <article>
                  <small>CATEGORÍA</small>
                  <table className="class-metrics">
                    <thead>
                      <tr>
                        <th>MÉTRICA</th>
                        <th>VALOR</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Accuracy</td>
                        <td>{((externo.accuracy ?? 0) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr>
                        <td>Precision macro</td>
                        <td>{((externo.precision_macro ?? 0) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr>
                        <td>Recall macro</td>
                        <td>{((externo.recall_macro ?? 0) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr>
                        <td>
                          <b>F1 macro</b>
                        </td>
                        <td>
                          <b>{((externo.f1_macro ?? 0) * 100).toFixed(1)}%</b>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </article>
                <article>
                  <small>PRIORIDAD</small>
                  <table className="class-metrics">
                    <thead>
                      <tr>
                        <th>MÉTRICA</th>
                        <th>VALOR</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Accuracy</td>
                        <td>{((externo.accuracy_prioridad ?? 0) * 100).toFixed(1)}%</td>
                      </tr>
                      <tr>
                        <td>
                          <b>F1 macro</b>
                        </td>
                        <td>
                          <b>{((externo.f1_prioridad ?? 0) * 100).toFixed(1)}%</b>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </article>
              </div>
              <p className="zone-empty">
                Estas cifras pueden ser distintas (normalmente más bajas) que las del conjunto
                fijo: reflejan el desempeño sobre textos no vistos y con otro vocabulario.
              </p>
            </div>
          ) : null}

          <div className="model-detail-grid">
            <article>
              <small>CURVA COBERTURA-PRECISIÓN (ELECCIÓN DEL UMBRAL DE REVISIÓN)</small>
              <CurvaCobertura puntos={cobertura} umbral={umbralesRevision.confianza} />
              <p>
                Umbral en uso: confianza ≥ <b>{umbralesRevision.confianza ?? "—"}</b> y margen ≥{" "}
                <b>{umbralesRevision.margen ?? "—"}</b>. Por debajo, el caso se marca como{" "}
                <b>requiere revisión humana</b>.
              </p>
            </article>
            <article>
              <small>CALIBRACIÓN DE LA CONFIANZA (¿“70 %” significa 70 % de acierto?)</small>
              {calibracion.tabla && calibracion.tabla.length > 0 ? (
                <>
                  <table className="class-metrics">
                    <thead>
                      <tr>
                        <th>RANGO</th>
                        <th>N</th>
                        <th>CONF. MEDIA</th>
                        <th>ACIERTO</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calibracion.tabla.map((fila) => (
                        <tr key={`${fila.rango[0]}-${fila.rango[1]}`}>
                          <td>
                            {fila.rango[0].toFixed(2)}–{fila.rango[1].toFixed(2)}
                          </td>
                          <td>{fila.n}</td>
                          <td>
                            {fila.confianza_media !== null
                              ? `${(fila.confianza_media * 100).toFixed(1)}%`
                              : "—"}
                          </td>
                          <td>
                            {fila.exactitud !== null ? `${(fila.exactitud * 100).toFixed(1)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p>
                    Brier score: <b>{calibracion.brier ?? "—"}</b> · ECE:{" "}
                    <b>{calibracion.ece ?? "—"}</b> (más bajo = mejor calibrado).
                  </p>
                </>
              ) : (
                <p className="zone-empty">Sin datos de calibración para esta versión.</p>
              )}
            </article>
          </div>

          <div className="lexicon-grid">
            <article>
              <small>ANÁLISIS DE ERRORES (CASOS MAL CLASIFICADOS DEL CONJUNTO DE PRUEBA)</small>
              {errores.length > 0 ? (
                <div className="error-list">
                  {errores.slice(0, 10).map((caso, indice) => (
                    <div key={`${caso.real}-${caso.predicha}-${indice}`}>
                      <p>{caso.texto}</p>
                      <span>
                        real <b>{caso.real}</b> → predicho <b>{caso.predicha}</b> · confianza{" "}
                        <b>{(caso.confianza * 100).toFixed(1)}%</b>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="zone-empty">
                  Ningún caso mal clasificado por encima del límite reportado en esta evaluación.
                </p>
              )}
            </article>
            <article>
              <small>CALIDAD DEL DATASET Y CONSISTENCIA DEL ETIQUETADO</small>
              {calidad && (
                <div className="distribution-list">
                  <div>
                    <span>Etiquetas vigentes</span>
                    <b>{calidad.total}</b>
                  </div>
                  <div>
                    <span>Duplicados exactos (grupos)</span>
                    <b>{calidad.duplicados_exactos?.grupos ?? 0}</b>
                  </div>
                  <div>
                    <span>Casi-duplicados (grupos)</span>
                    <b>{calidad.casi_duplicados?.n_grupos_con_duplicados ?? 0}</b>
                  </div>
                  <div>
                    <span>Casi-duplicados (registros extra)</span>
                    <b>{calidad.casi_duplicados?.registros_extra ?? 0}</b>
                  </div>
                  <div>
                    <span>Etiquetas contradictorias</span>
                    <b>{calidad.etiquetas_contradictorias?.n ?? 0}</b>
                  </div>
                  <div>
                    <span>Vocabulario único</span>
                    <b>{calidad.vocabulario_unico}</b>
                  </div>
                  <div>
                    <span>Razón max/min por clase</span>
                    <b>
                      {calidad.desbalance?.razon_max_min !== null &&
                      calidad.desbalance?.razon_max_min !== undefined
                        ? calidad.desbalance.razon_max_min.toFixed(2)
                        : "—"}
                    </b>
                  </div>
                </div>
              )}
              <p>
                Casi-duplicados detectados al reservar la prueba (umbral{" "}
                <b>{casiDuplicados.umbral ?? "0.85"}</b>): <b>{casiDuplicados.n_grupos_con_duplicados ?? 0}</b>{" "}
                grupos, <b>{casiDuplicados.registros_extra ?? 0}</b> registros extra.
              </p>
              <div className="subsection-title">ACUERDO ENTRE ETIQUETADORES (KAPPA DE COHEN)</div>
              {acuerdo && acuerdo.n_solicitudes_dobles > 0 ? (
                <div className="distribution-list">
                  <div>
                    <span>Kappa categoría</span>
                    <b>{acuerdo.kappa_categoria !== null ? acuerdo.kappa_categoria.toFixed(3) : "—"}</b>
                  </div>
                  <div>
                    <span>Kappa prioridad</span>
                    <b>{acuerdo.kappa_prioridad !== null ? acuerdo.kappa_prioridad.toFixed(3) : "—"}</b>
                  </div>
                  <div>
                    <span>Solicitudes con 2+ etiquetas</span>
                    <b>{acuerdo.n_solicitudes_dobles}</b>
                  </div>
                  <div>
                    <span>Etiquetadores</span>
                    <b>{acuerdo.n_etiquetadores}</b>
                  </div>
                </div>
              ) : (
                <p className="zone-empty">
                  {acuerdo?.mensaje ??
                    "Aún no hay solicitudes etiquetadas por dos o más personas; no se puede calcular kappa."}
                </p>
              )}
            </article>
          </div>

          <div className="versions-card">
            <div className="section-title">
              <div>
                <h3>MEJORA POR VOLUMEN DE ETIQUETAS</h3>
                <p>
                  F1 macro medio ± desviación estándar (5 semillas) sobre el MISMO conjunto de
                  prueba, submuestreando datos de entrenamiento.
                </p>
              </div>
              {mejoraPuntos?.resultado.algoritmo && (
                <span className="stable">
                  <i /> {mejoraPuntos.resultado.algoritmo}
                </span>
              )}
            </div>
            <GraficoMejora puntos={mejoraPuntos?.resultado.puntos} />
            {mejoraPuntos?.resultado.metodologia && (
              <p className="zone-empty">{mejoraPuntos.resultado.metodologia}</p>
            )}
          </div>

          <div className="lexicon-grid">
            <article>
              <small>COMPARACIÓN DE ALGORITMOS · CATEGORÍA</small>
              {Object.keys(comparacionCat).length > 0 ? (
                <div className="distribution-list">
                  {Object.entries(comparacionCat).map(([nombre, metrica]) => (
                    <div key={nombre}>
                      <span>{nombre}</span>
                      <i>
                        <em style={{ width: `${metrica.f1_macro * 100}%` }} />
                      </i>
                      <b>{(metrica.f1_macro * 100).toFixed(1)}%</b>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="zone-empty">Sin comparación registrada.</p>
              )}
              <p>
                Seleccionado por F1 macro mediante validación cruzada estratificada. Ganador:{" "}
                <b className="online-text">{modelo.algoritmo}</b>
              </p>
            </article>
            <article>
              <small>COMPARACIÓN DE ALGORITMOS · PRIORIDAD</small>
              {Object.keys(comparacionPri).length > 0 ? (
                <div className="distribution-list">
                  {Object.entries(comparacionPri).map(([nombre, metrica]) => (
                    <div key={nombre}>
                      <span>{nombre}</span>
                      <i>
                        <em style={{ width: `${metrica.f1_macro * 100}%` }} />
                      </i>
                      <b>{(metrica.f1_macro * 100).toFixed(1)}%</b>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="zone-empty">Sin comparación registrada.</p>
              )}
              <p>
                Clasificador de prioridad entrenado con la misma técnica (ALTA / MEDIA / BAJA).
              </p>
            </article>
          </div>

          <div className="lexicon-grid">
            <article>
              <small>TÉRMINOS MÁS INFLUYENTES POR CATEGORÍA</small>
              <div className="terms-grid">
                {terminosPorCategoria.map(([clave, terminos]) => (
                  <div key={clave}>
                    <b>
                      <Icon name={(iconosPorClave.get(clave) ?? "bolt") as IconName} size={13} />{" "}
                      {nombresPorClave.get(clave) ?? clave}
                    </b>
                    <div className="bigram-list">
                      {terminos.slice(0, 6).map((termino) => (
                        <span key={termino.termino}>
                          {termino.termino} <small>{termino.peso.toFixed(2)}</small>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </article>
            <article>
              <small>EVOLUCIÓN DEL F1 MACRO POR VERSIÓN</small>
              <EvolucionVersiones versiones={versiones} />
            </article>
          </div>

          <div className="versions-card">
            <div className="section-title">
              <div>
                <h3>HISTORIAL DE VERSIONES</h3>
                <p>Cada versión se guarda en la base de datos con su binario y sus métricas</p>
              </div>
              {onDemo && (
                <button onClick={onDemo}>EJECUTAR DEMOSTRACIÓN NLP</button>
              )}
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>VERSIÓN</th>
                    <th>FECHA</th>
                    <th>ALGORITMO</th>
                    <th>TRAIN</th>
                    <th>TEST</th>
                    <th>F1 MACRO</th>
                    <th>ESTADO</th>
                    <th>ACCIÓN</th>
                  </tr>
                </thead>
                <tbody>
                  {versiones.map((version) => (
                    <tr key={version.version}>
                      <td>
                        <b>{version.version}</b>
                      </td>
                      <td>{new Date(version.fecha).toLocaleString("es-BO")}</td>
                      <td>{version.algoritmo}</td>
                      <td>{version.n_entrenamiento}</td>
                      <td>{version.n_prueba || version.n_validacion}</td>
                      <td>
                        <b className="confidence-cell">
                          {(version.f1_macro * 100).toFixed(1)}%
                        </b>
                      </td>
                      <td>
                        {version.activo ? (
                          <span className="state resuelto">
                            <i /> ACTIVA
                          </span>
                        ) : version.valida_para_comparacion === false ? (
                          <span
                            className="state en-proceso"
                            title={`No comparable: ${version.motivo_invalidez || "entrenada con datos del conjunto de prueba"}`}
                          >
                            <i /> NO COMPARABLE
                          </span>
                        ) : (
                          <span className="state en-proceso">
                            <i /> Archivo
                          </span>
                        )}
                      </td>
                      <td>
                        <button
                          className="nlp-button"
                          disabled={version.activo}
                          title={
                            version.valida_para_comparacion === false
                              ? `Versión no comparable (${version.motivo_invalidez || "fuga de datos"}); requiere forzar la activación.`
                              : undefined
                          }
                          onClick={() => void activar(version.version, version.valida_para_comparacion === false)}
                        >
                          {version.activo
                            ? "EN USO"
                            : version.valida_para_comparacion === false
                              ? "ACTIVAR (FORZAR)"
                              : "ACTIVAR (ROLLBACK)"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* B2 · Configuración y parámetros reales del modelo activo */}
          {parametros && (
            <div className="versions-card parametros-card">
              <div className="section-title">
                <div>
                  <h3>CONFIGURACIÓN Y PARÁMETROS DEL MODELO ACTIVO</h3>
                  <p>
                    Valores reales leídos del binario desplegado y de su registro de entrenamiento:
                    todo lo que el agente usa para clasificar queda visible y verificable.
                  </p>
                </div>
                <span className="stable">
                  <i /> {parametros.version}
                </span>
              </div>

              <div className="parametros-grid">
                <article className="parametro-bloque">
                  <small>ALGORITMOS</small>
                  <ParametroFila
                    etiqueta="Clasificador de categoría"
                    valor={parametros.algoritmo_categoria}
                  />
                  <ParametroFila
                    etiqueta="Clasificador de prioridad"
                    valor={parametros.algoritmo_prioridad}
                  />
                  <ParametroFila etiqueta="Método de evaluación" valor={parametros.metodo_evaluacion} />
                  <ParametroFila
                    etiqueta="Versión del conjunto de prueba"
                    valor={parametros.version_prueba}
                  />
                </article>

                <article className="parametro-bloque">
                  <small>HIPERPARÁMETROS · CATEGORÍA</small>
                  <ParametroFila
                    etiqueta="C (regularización)"
                    valor={formatearParametro(parametros.hiperparametros.categoria.C)}
                  />
                  <ParametroFila
                    etiqueta="alpha"
                    valor={formatearParametro(parametros.hiperparametros.categoria.alpha)}
                  />
                  <ParametroFila
                    etiqueta="class_weight"
                    valor={formatearParametro(parametros.hiperparametros.categoria.class_weight)}
                  />
                  <ParametroFila
                    etiqueta="max_iter"
                    valor={formatearParametro(parametros.hiperparametros.categoria.max_iter)}
                  />
                  <ParametroFila
                    etiqueta="Calibrado (Platt)"
                    valor={parametros.hiperparametros.categoria.calibrado ? "sí" : "no"}
                  />
                </article>

                <article className="parametro-bloque">
                  <small>HIPERPARÁMETROS · PRIORIDAD</small>
                  <ParametroFila
                    etiqueta="C (regularización)"
                    valor={formatearParametro(parametros.hiperparametros.prioridad.C)}
                  />
                  <ParametroFila
                    etiqueta="alpha"
                    valor={formatearParametro(parametros.hiperparametros.prioridad.alpha)}
                  />
                  <ParametroFila
                    etiqueta="class_weight"
                    valor={formatearParametro(parametros.hiperparametros.prioridad.class_weight)}
                  />
                  <ParametroFila
                    etiqueta="max_iter"
                    valor={formatearParametro(parametros.hiperparametros.prioridad.max_iter)}
                  />
                  <ParametroFila
                    etiqueta="Calibrado (Platt)"
                    valor={parametros.hiperparametros.prioridad.calibrado ? "sí" : "no"}
                  />
                </article>

                <article className="parametro-bloque">
                  <small>VECTORIZADOR TF-IDF (Ec.1–3)</small>
                  <ParametroFila
                    etiqueta="n-gramas"
                    valor={`${parametros.tfidf.ngram_range[0]}–${parametros.tfidf.ngram_range[1]}`}
                  />
                  <ParametroFila
                    etiqueta="min_df"
                    valor={formatearParametro(parametros.tfidf.min_df)}
                  />
                  <ParametroFila
                    etiqueta="sublinear_tf"
                    valor={formatearParametro(parametros.tfidf.sublinear_tf)}
                  />
                  <ParametroFila
                    etiqueta="Características (categoría)"
                    valor={String(parametros.tfidf.n_caracteristicas)}
                  />
                  <ParametroFila
                    etiqueta="Vocabulario"
                    valor={String(parametros.tfidf.tamano_vocabulario)}
                  />
                  <ParametroFila
                    etiqueta="Características (prioridad)"
                    valor={String(parametros.tfidf.n_caracteristicas_prioridad)}
                  />
                </article>

                <article className="parametro-bloque">
                  <small>DIVISIÓN DE DATOS</small>
                  <ParametroFila etiqueta="Semilla" valor={String(parametros.division.semilla)} />
                  <ParametroFila
                    etiqueta="Entrenamiento"
                    valor={`${parametros.division.entrenamiento} casos`}
                  />
                  <ParametroFila
                    etiqueta="Prueba fija"
                    valor={`${parametros.division.prueba_fija} casos`}
                  />
                  <ParametroFila
                    etiqueta="Prueba externa"
                    valor={`${parametros.division.prueba_externa} casos`}
                  />
                  <ParametroFila etiqueta="Folds máx." valor={String(parametros.division.folds_max)} />
                  <p className="zone-empty">{parametros.division.esquema}</p>
                </article>

                <article className="parametro-bloque">
                  <small>UMBRALES DE DECISIÓN (Ec.9)</small>
                  <ParametroFila
                    etiqueta="Confianza mínima"
                    valor={`${parametros.umbrales.confianza}%`}
                  />
                  <ParametroFila etiqueta="Margen mínimo" valor={`${parametros.umbrales.margen}%`} />
                  <p className="zone-empty">
                    Por debajo de estos umbrales la solicitud se marca como{" "}
                    <b>requiere revisión humana</b>.
                  </p>
                </article>

                <article className="parametro-bloque">
                  <small>EFICIENCIA MEDIDA (Fase A3)</small>
                  <ParametroFila
                    etiqueta="Tiempo de entrenamiento"
                    valor={formatearNumero(parametros.eficiencia.tiempo_entrenamiento_s, " s")}
                  />
                  <ParametroFila
                    etiqueta="Tamaño del modelo"
                    valor={formatearNumero(parametros.eficiencia.tamano_modelo_kb, " KB")}
                  />
                  <ParametroFila
                    etiqueta="Latencia media"
                    valor={formatearNumero(parametros.eficiencia.latencia_media_ms, " ms")}
                  />
                  <ParametroFila
                    etiqueta="Latencia p95"
                    valor={formatearNumero(parametros.eficiencia.latencia_p95_ms, " ms")}
                  />
                  <ParametroFila
                    etiqueta="Predicciones medidas"
                    valor={String(parametros.eficiencia.n_predicciones ?? "—")}
                  />
                </article>
              </div>

              <div className="subsection-title">ECUACIONES DE LOS PARÁMETROS Y UMBRALES</div>
              <EcuacionLista numeros={[1, 2, 3, 4, 6, 7, 8, 9]} compacto />
            </div>
          )}

          {/* B4 · Ciclo de mejora continua del agente */}
          <div className="versions-card ciclo-card">
            <div className="section-title">
              <div>
                <h3>CICLO DE MEJORA CONTINUA</h3>
                <p>
                  El agente no es estático: cada nueva etiqueta real reentrena y reevalúa el modelo
                  bajo las mismas reglas, de modo que las mejoras se comparan objetivamente.
                </p>
              </div>
              <span className="stable">
                <i /> versión activa {modelo.version}
              </span>
            </div>
            <div className="ciclo-mejora">
              {CICLO_MEJORA.map((paso) => (
                <article key={paso.numero}>
                  <span>{String(paso.numero).padStart(2, "0")}</span>
                  <h4>{paso.titulo}</h4>
                  <b>{paso.detalle}</b>
                  <p>{paso.descripcion}</p>
                </article>
              ))}
            </div>
            <p className="zone-empty">
              Cada versión se guarda con sus ids de entrenamiento y el indicador{" "}
              <b>valida_para_comparacion</b>, que impide activar un modelo entrenado con el conjunto
              de prueba.
            </p>
          </div>

          {/* B5 · Informe del agente (Markdown, JSON y ZIP) */}
          <InformeCard onNotice={onNotice} />
        </>
      )}

      <div className="training-explanation">
        <div>
          <span>APRENDIZAJE SUPERVISADO</span>
          <h3>¿Qué significa “supervisado”?</h3>
          <p>
            Durante el entrenamiento, cada ejemplo ya tiene una respuesta correcta asignada por una
            persona experta. El algoritmo aprende la relación entre las palabras del reclamo y esa
            etiqueta, y luego aplica ese patrón a solicitudes nuevas que nunca había visto.
          </p>
        </div>
        <div className="training-example">
          <span>ENTRADA ETIQUETADA</span>
          <p>“Fuga de agua en la avenida”</p>
          <i>↓ el modelo aprende la relación ↓</i>
          <b>Etiqueta: Agua potable y alcantarillado</b>
        </div>
      </div>
    </section>
  );
}
