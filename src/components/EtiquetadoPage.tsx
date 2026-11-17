import { useCallback, useEffect, useState } from "react";
import type {
  Categoria,
  ColaEtiquetado,
  Estadisticas,
  GuiaEtiquetado,
  IconName,
  Priority,
  Solicitud,
} from "@/types";
import {
  etiquetarSolicitud,
  listarCategorias,
  obtenerCola,
  obtenerEstadisticas,
  obtenerGuia,
} from "@/lib/api";
import { Icon } from "@/components/Icon";

const PRIORIDADES: Priority[] = ["ALTA", "MEDIA", "BAJA"];

/**
 * Sección de ETIQUETADO (aprendizaje activo).
 *
 * Muestra la cola priorizada por el backend (primero las solicitudes sin etiqueta
 * con menor confianza y menor margen), la guía de criterios y el progreso real
 * por categoría hacia la meta. Permite confirmar la predicción con un clic o
 * corregirla, registrando siempre quién etiqueta.
 */
export function EtiquetadoPage({
  onNotice,
  onInspect,
  onBack,
}: {
  onNotice: (message: string) => void;
  onInspect: (solicitud: Solicitud) => void;
  onBack: () => void;
}) {
  const [cola, setCola] = useState<ColaEtiquetado | null>(null);
  const [guia, setGuia] = useState<GuiaEtiquetado | null>(null);
  const [stats, setStats] = useState<Estadisticas | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [etiquetador, setEtiquetador] = useState("Equipo # 3");
  const [editando, setEditando] = useState<number | null>(null);
  const [categoriaManual, setCategoriaManual] = useState<string>("");
  const [prioridadManual, setPrioridadManual] = useState<Priority>("MEDIA");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState<number | null>(null);

  /** Recarga la cola, la guía, las estadísticas y el catálogo de categorías. */
  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const [nuevaCola, nuevaGuia, nuevasStats, nuevoCatalogo] = await Promise.all([
        obtenerCola(25),
        obtenerGuia(),
        obtenerEstadisticas(),
        listarCategorias(),
      ]);
      setCola(nuevaCola);
      setGuia(nuevaGuia);
      setStats(nuevasStats);
      setCategorias(nuevoCatalogo);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo cargar la cola de etiquetado.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  /** Registra una etiqueta y refresca la cola y el progreso. */
  const guardarEtiqueta = useCallback(
    async (solicitud: Solicitud, categoriaClave: string, prioridad: Priority) => {
      setGuardando(solicitud.id);
      try {
        await etiquetarSolicitud(solicitud.id, {
          categoria_clave: categoriaClave,
          prioridad,
          etiquetado_por: etiquetador.trim(),
        });
        onNotice(`${solicitud.ticket} etiquetada como ${categoriaClave} · ${prioridad}`);
        setEditando(null);
        await cargar();
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo guardar la etiqueta.");
      } finally {
        setGuardando(null);
      }
    },
    [cargar, etiquetador, onNotice],
  );

  const iconosPorClave = new Map(categorias.map((c) => [c.clave, c.icono]));

  return (
    <section className="module-page">
      <div className="module-heading">
        <div>
          <button className="module-back" onClick={onBack} type="button">
            <span aria-hidden="true">←</span> VOLVER AL PANEL ADMINISTRATIVO
          </button>
          <span>MÓDULO DE ENTRENAMIENTO SUPERVISADO</span>
          <h2>Etiquetado de solicitudes</h2>
          <p>
            Confirma o corrige la categoría y la prioridad de cada solicitud. Cada etiqueta
            alimenta el siguiente entrenamiento del agente.
          </p>
        </div>
        <button onClick={() => void cargar()} disabled={cargando}>
          {cargando ? "CARGANDO…" : "ACTUALIZAR COLA"}
        </button>
      </div>

      {stats && !stats.datos_suficientes && (
        <div className="alert-banner warn">
          <Icon name="bolt" size={16} />
          <span>
            <b>Datos insuficientes.</b> Hay categorías con menos de 30 etiquetas: el modelo se
            evalúa con validación cruzada y sus métricas son orientativas. Etiqueta más solicitudes
            para estabilizar el clasificador (meta: 50 por categoría).
          </span>
        </div>
      )}

      {error && (
        <div className="alert-banner error">
          <Icon name="bolt" size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="etiquetado-layout">
        <div className="etiquetado-main">
          <div className="etiquetador-field">
            <label>
              ¿Quién etiqueta?
              <input
                value={etiquetador}
                onChange={(event) => setEtiquetador(event.target.value)}
                placeholder="Nombre del integrante del equipo"
                maxLength={120}
              />
            </label>
            {cola && (
              <span className="cola-resumen">
                <b>{cola.total_pendientes}</b> pendientes · meta {cola.meta_por_categoria} por
                categoría
              </span>
            )}
          </div>

          <div className="queue-list">
            {cargando && <p className="zone-empty">Cargando cola priorizada…</p>}
            {!cargando && cola?.items.length === 0 && (
              <p className="zone-empty">
                No hay solicitudes pendientes de etiquetar. ¡Buen trabajo!
              </p>
            )}
            {cola?.items.map((solicitud) => {
              const enEdicion = editando === solicitud.id;
              const sugerida = solicitud.sugerencia_confirmar;
              const prioridadSugerida = solicitud.prioridad_predicha ?? "MEDIA";
              return (
                <article className={`queue-item ${enEdicion ? "editing" : ""}`} key={solicitud.id}>
                  <div className="queue-head">
                    <div>
                      <b>{solicitud.ticket}</b>
                      <span className="queue-otb">
                        <Icon name="map" size={13} /> {solicitud.otb} · {solicitud.zona}
                      </span>
                    </div>
                    <button
                      className="queue-inspect"
                      onClick={() => onInspect(solicitud)}
                      title="Ver trazabilidad NLP"
                    >
                      VER NLP
                    </button>
                  </div>
                  <p>{solicitud.texto}</p>
                  <div className="queue-pred">
                    <span>
                      PREDICHO{" "}
                      <b>
                        <Icon
                          name={(iconosPorClave.get(sugerida ?? "") ?? "bolt") as IconName}
                          size={13}
                        />{" "}
                        {solicitud.categoria_predicha_nombre ?? "Sin categoría"}
                      </b>
                    </span>
                    <span className={`priority ${prioridadSugerida.toLowerCase()}`}>
                      <i /> {prioridadSugerida}
                    </span>
                    <span className="queue-confidence">
                      CONFIANZA <b>{solicitud.confianza?.toFixed(1) ?? "—"}%</b>
                    </span>
                    {solicitud.margen !== null && solicitud.margen !== undefined && (
                      <span className="queue-margin">
                        MARGEN <b>{solicitud.margen.toFixed(1)}%</b>
                      </span>
                    )}
                  </div>

                  {!enEdicion ? (
                    <div className="queue-actions">
                      <button
                        className="confirm"
                        disabled={!sugerida || guardando === solicitud.id}
                        onClick={() =>
                          sugerida && void guardarEtiqueta(solicitud, sugerida, prioridadSugerida)
                        }
                      >
                        <Icon name="check" size={15} /> CONFIRMAR PREDICCIÓN
                      </button>
                      <button
                        className="correct"
                        onClick={() => {
                          setEditando(solicitud.id);
                          setCategoriaManual(sugerida ?? "");
                          setPrioridadManual(prioridadSugerida);
                        }}
                      >
                        CORREGIR ETIQUETA
                      </button>
                    </div>
                  ) : (
                    <div className="queue-form">
                      <label>
                        CATEGORÍA CORRECTA
                        <select
                          value={categoriaManual}
                          onChange={(event) => setCategoriaManual(event.target.value)}
                        >
                          <option value="">Seleccionar…</option>
                          {categorias.map((categoria) => (
                            <option key={categoria.clave} value={categoria.clave}>
                              {categoria.nombre}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        PRIORIDAD
                        <div className="priority-picker">
                          {PRIORIDADES.map((nivel) => (
                            <button
                              className={`${nivel.toLowerCase()} ${
                                prioridadManual === nivel ? "active" : ""
                              }`}
                              onClick={() => setPrioridadManual(nivel)}
                              key={nivel}
                            >
                              {nivel}
                            </button>
                          ))}
                        </div>
                      </label>
                      <div className="queue-form-actions">
                        <button
                          className="confirm"
                          disabled={!categoriaManual || guardando === solicitud.id}
                          onClick={() =>
                            void guardarEtiqueta(solicitud, categoriaManual, prioridadManual)
                          }
                        >
                          <Icon name="check" size={15} /> GUARDAR ETIQUETA
                        </button>
                        <button className="cancel" onClick={() => setEditando(null)}>
                          CANCELAR
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>

        <aside className="etiquetado-side">
          {guia && (
            <article className="guide-card">
              <div className="section-title">
                <div>
                  <h3>GUÍA DE CRITERIOS</h3>
                  <p>Cómo etiquetar de forma consistente</p>
                </div>
              </div>
              <div className="guide-block">
                <small>PRIORIDAD</small>
                {guia.prioridades.map((item) => (
                  <div className="guide-row" key={item.nivel}>
                    <span className={`priority ${item.nivel.toLowerCase()}`}>
                      <i /> {item.nivel}
                    </span>
                    <p>{item.criterio}</p>
                  </div>
                ))}
              </div>
              <div className="guide-block">
                <small>DESAMBIGUACIÓN ENTRE CATEGORÍAS</small>
                {guia.desambiguaciones.map((item) => (
                  <div className="guide-row" key={item.categoria}>
                    <b>{item.categoria}</b>
                    <p>{item.criterio}</p>
                  </div>
                ))}
              </div>
            </article>
          )}

          {stats && (
            <article className="progress-card">
              <div className="section-title">
                <div>
                  <h3>PROGRESO HACIA LA META</h3>
                  <p>
                    {stats.etiquetadas} etiquetadas de {stats.total_solicitudes} · meta{" "}
                    {guia?.meta_por_categoria ?? 50} por categoría
                  </p>
                </div>
              </div>
              <div className="progress-list">
                {stats.progreso_por_categoria.map((item) => {
                  const porcentaje = Math.min(100, (item.etiquetadas / item.meta) * 100);
                  return (
                    <div className={item.faltan === 0 ? "done" : ""} key={item.clave}>
                      <span>
                        <Icon
                          name={(iconosPorClave.get(item.clave) ?? "bolt") as IconName}
                          size={13}
                        />{" "}
                        {item.nombre}
                      </span>
                      <i>
                        <em style={{ width: `${porcentaje}%` }} />
                      </i>
                      <b>{item.etiquetadas}</b>
                      <small>
                        {item.faltan === 0
                          ? "Meta alcanzada"
                          : `Faltan ${item.faltan} para llegar a ${item.meta}`}
                      </small>
                    </div>
                  );
                })}
              </div>
              {stats.por_etiquetador.length > 0 && (
                <div className="guide-block">
                  <small>APORTE POR ETIQUETADOR</small>
                  {stats.por_etiquetador.map((persona) => (
                    <div className="guide-row compact" key={persona.nombre}>
                      <b>{persona.nombre}</b>
                      <p>{persona.total} etiquetas</p>
                    </div>
                  ))}
                </div>
              )}
            </article>
          )}
        </aside>
      </div>
    </section>
  );
}
