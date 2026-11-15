import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Categoria,
  EntrenarResponse,
  Estadisticas,
  GuiaEtiquetado,
  IconName,
  Modelo,
} from "@/types";
import {
  activarVersion,
  entrenarModelo,
  listarCategorias,
  listarVersiones,
  modeloActivo,
  obtenerEstadisticas,
  obtenerGuia,
} from "@/lib/api";
import { Icon } from "@/components/Icon";

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

/** Gráfico de evolución del F1 macro a lo largo de las versiones del modelo. */
function EvolucionVersiones({ versiones }: { versiones: Modelo[] }) {
  const ordenadas = [...versiones].reverse();
  if (ordenadas.length < 2) {
    return (
      <p className="zone-empty">
        Se necesita más de una versión para mostrar la evolución. Reentrena el agente tras
        etiquetar nuevas solicitudes.
      </p>
    );
  }
  return (
    <div className="version-evolution">
      {ordenadas.map((modelo, indice) => {
        const altura = Math.max(4, modelo.f1_macro * 100);
        return (
          <div className={modelo.activo ? "active" : ""} key={modelo.version}>
            <i style={{ height: `${altura}%`, background: COLORES_VERSION[indice % 6] }} />
            <b>{(modelo.f1_macro * 100).toFixed(1)}%</b>
            <span>{modelo.version}</span>
            <small>{modelo.n_entrenamiento} casos</small>
          </div>
        );
      })}
    </div>
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
    async (version: string) => {
      try {
        await activarVersion(version);
        onNotice(`Versión ${version} activada (rollback).`);
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
                {modelo.n_entrenamiento + modelo.n_validacion + modelo.n_prueba}{" "}
                <span>casos etiquetados</span>
              </h3>
              <p>
                Solicitudes reales etiquetadas por el equipo y almacenadas en Supabase. El conjunto
                de prueba fijo nunca se usa para entrenar.
              </p>
              <div className="dataset-split">
                <span>
                  <i style={{ width: "70%" }} />
                  {modelo.n_entrenamiento} Entrenamiento
                </span>
                <span>
                  <i style={{ width: "15%" }} />
                  {modelo.n_validacion} Validación
                </span>
                <span>
                  <i style={{ width: "15%" }} />
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
              {etiquetasMatriz.length > 0 && valoresMatriz.length > 0 ? (
                <div className="confusion-scroll">
                  <table className="confusion-table">
                    <thead>
                      <tr>
                        <th>real \ pred</th>
                        {etiquetasMatriz.map((clave) => (
                          <th key={clave}>{ABREVIATURA[clave] ?? clave.slice(0, 4)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {valoresMatriz.map((fila, i) => (
                        <tr key={etiquetasMatriz[i] ?? i}>
                          <th>{ABREVIATURA[etiquetasMatriz[i]] ?? etiquetasMatriz[i] ?? i}</th>
                          {fila.map((valor, j) => (
                            <td
                              className={i === j ? "hot" : valor > 0 ? "warm" : ""}
                              key={j}
                              title={`${etiquetasMatriz[i]} → ${etiquetasMatriz[j]}: ${valor}`}
                            >
                              {valor}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="zone-empty">Sin matriz disponible para esta versión.</p>
              )}
              <p>La diagonal (celdas resaltadas) muestra las predicciones correctas.</p>
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
                        <span className={`state ${version.activo ? "resuelto" : "en-proceso"}`}>
                          <i /> {version.activo ? "ACTIVA" : "Archivada"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="nlp-button"
                          disabled={version.activo}
                          onClick={() => void activar(version.version)}
                        >
                          {version.activo ? "EN USO" : "ACTIVAR (ROLLBACK)"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
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
