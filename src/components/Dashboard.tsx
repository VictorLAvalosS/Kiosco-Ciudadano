import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  AdminSection,
  Categoria,
  Estadisticas,
  Modelo,
  Priority,
  Salud,
  Solicitud,
} from "@/types";
import {
  asignarSolicitud,
  cambiarEstado,
  etiquetarSolicitud,
  generarInforme,
  listarCategorias,
  listarSolicitudes,
  modeloActivo,
  obtenerEstadisticas,
  obtenerSalud,
} from "@/lib/api";
import { crewForCategory, relativeTime } from "@/lib/catalogos";
import { Icon } from "@/components/Icon";
import { Brand } from "@/components/shared";
import { ModelPage } from "@/components/ModelPage";
import { EtiquetadoPage } from "@/components/EtiquetadoPage";
import { PruebaAgente } from "@/components/PruebaAgente";
import { CrewsPage, MapPage } from "@/components/OperationsModules";
import { Navar, type SubseccionModelo } from "@/components/navar";

type UtilityPanel = "settings" | "support" | "profile" | null;

const PAGE_SIZE = 12;

/** Prioridad efectiva de una solicitud (etiqueta humana > predicción del modelo). */
function prioridadDe(solicitud: Solicitud): Priority | null {
  return solicitud.etiqueta?.prioridad ?? solicitud.prioridad_predicha;
}

/** Nombre de categoría efectivo de una solicitud. */
function categoriaDe(solicitud: Solicitud): string {
  return solicitud.etiqueta?.categoria_nombre ?? solicitud.categoria_predicha_nombre ?? "Sin clasificar";
}

const SECTION_TITLES: Record<AdminSection, [string, string]> = {
  overview: ["Clasificador de", "solicitudes ciudadanas"],
  requests: ["Gestión de", "solicitudes"],
  etiquetado: ["Entrenamiento", "del agente"],
  map: ["Mapa territorial", "de OTBs"],
  crews: ["Gestión de", "cuadrillas"],
  prueba: ["Prueba del", "agente en vivo"],
  model: ["Laboratorio de", "inteligencia artificial"],
};

export function Dashboard({
  onKiosk,
  onInspect,
}: {
  onKiosk: () => void;
  onInspect: (solicitud: Solicitud) => void;
}) {
  const [light, setLight] = useState(false);
  const [filter, setFilter] = useState("Todas");
  const [search, setSearch] = useState("");
  const [activeSection, setActiveSection] = useState<AdminSection>("overview");
  const [subseccionModelo, setSubseccionModelo] = useState<SubseccionModelo>("resumen");
  const [pagina, setPagina] = useState(1);
  const [notice, setNotice] = useState("");
  const [utilityPanel, setUtilityPanel] = useState<UtilityPanel>(null);

  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [stats, setStats] = useState<Estadisticas | null>(null);
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [salud, setSalud] = useState<Salud | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  // Estado del formulario de etiquetado (confirmar / corregir desde el panel).
  const [etiquetando, setEtiquetando] = useState<Solicitud | null>(null);
  const [categoriaManual, setCategoriaManual] = useState("");
  const [prioridadManual, setPrioridadManual] = useState<Priority>("MEDIA");
  const [guardando, setGuardando] = useState(false);
  const [etiquetador, setEtiquetador] = useState("Equipo # 3");

  const showNotice = useCallback((message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(""), 2600);
  }, []);

  /** Carga todas las fuentes reales de datos del panel. */
  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const [nuevasSolicitudes, nuevasStats, activo, nuevoCatalogo, nuevoSalud] =
        await Promise.all([
          listarSolicitudes({ limite: 300 }),
          obtenerEstadisticas(),
          modeloActivo(),
          listarCategorias(),
          obtenerSalud().catch(() => null),
        ]);
      setSolicitudes(nuevasSolicitudes);
      setStats(nuevasStats);
      setModelo(activo);
      setCategorias(nuevoCatalogo);
      setSalud(nuevoSalud);
    } catch (fallo) {
      setError(
        fallo instanceof Error
          ? fallo.message
          : "No se pudieron cargar los datos desde la API.",
      );
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const metricas = useMemo(() => {
    const conConfianza = solicitudes.filter((s) => s.confianza !== null);
    const confianzaMedia =
      conConfianza.length > 0
        ? conConfianza.reduce((suma, s) => suma + (s.confianza ?? 0), 0) / conConfianza.length
        : 0;
    const conLatencia = solicitudes.filter((s) => s.latencia_ms !== null);
    const latenciaMedia =
      conLatencia.length > 0
        ? conLatencia.reduce((suma, s) => suma + (s.latencia_ms ?? 0), 0) / conLatencia.length
        : 0;
    const pendientes = solicitudes.filter((s) => s.estado === "Sin asignar");
    const pendientesAlta = pendientes.filter((s) => prioridadDe(s) === "ALTA");
    const abiertas = solicitudes.filter((s) => s.estado !== "Resuelto");
    return { confianzaMedia, latenciaMedia, pendientes, pendientesAlta, abiertas };
  }, [solicitudes]);

  const cargaOtb = useMemo(() => {
    const conteo = new Map<string, number>();
    solicitudes.forEach((s) => {
      const otb = s.otb || "Sin OTB";
      conteo.set(otb, (conteo.get(otb) ?? 0) + 1);
    });
    const entradas = [...conteo.entries()].map(([name, count]) => ({ name, count }));
    const max = Math.max(1, ...entradas.map((e) => e.count));
    return entradas
      .sort((a, b) => b.count - a.count)
      .map((item, index) => ({
        ...item,
        percent: `${Math.round((item.count / max) * 100)}%`,
        color: ["#00d9ff", "#5b8cff", "#805cff", "#19ce9a", "#f3b43f", "#ff7a59"][index % 6],
      }));
  }, [solicitudes]);

  const visible = useMemo(() => {
    const consulta = search.trim().toLowerCase();
    return solicitudes.filter((solicitud) => {
      const coincideFiltro =
        filter === "Todas" || prioridadDe(solicitud) === filter.toUpperCase();
      const coincideTexto =
        consulta.length === 0 ||
        `${solicitud.texto} ${solicitud.ticket} ${solicitud.otb} ${categoriaDe(solicitud)}`
          .toLowerCase()
          .includes(consulta);
      return coincideFiltro && coincideTexto;
    });
  }, [filter, search, solicitudes]);

  const totalPaginas = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const paginaActual = Math.min(pagina, totalPaginas);
  const filas = visible.slice((paginaActual - 1) * PAGE_SIZE, paginaActual * PAGE_SIZE);

  const asignar = useCallback(
    async (solicitud: Solicitud) => {
      const cuadrilla = crewForCategory(solicitud.categoria_predicha_clave ?? "")?.name ??
        "Cuadrilla general";
      try {
        await asignarSolicitud(solicitud.id, cuadrilla);
        showNotice(`${solicitud.ticket} asignada a ${cuadrilla}`);
        await cargar();
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo asignar la solicitud.");
      }
    },
    [cargar, showNotice],
  );

  const resolver = useCallback(
    async (solicitud: Solicitud) => {
      try {
        await cambiarEstado(solicitud.id, "Resuelto");
        showNotice(`${solicitud.ticket} marcada como resuelta`);
        await cargar();
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo cambiar el estado.");
      }
    },
    [cargar, showNotice],
  );

  const abrirEtiqueta = useCallback((solicitud: Solicitud) => {
    setEtiquetando(solicitud);
    setCategoriaManual(solicitud.categoria_predicha_clave ?? "");
    setPrioridadManual(prioridadDe(solicitud) ?? "MEDIA");
  }, []);

  const guardarEtiqueta = useCallback(
    async (solicitud: Solicitud, categoriaClave: string, prioridad: Priority) => {
      setGuardando(true);
      try {
        await etiquetarSolicitud(solicitud.id, {
          categoria_clave: categoriaClave,
          prioridad,
          etiquetado_por: etiquetador.trim(),
        });
        showNotice(`${solicitud.ticket} etiquetada correctamente`);
        setEtiquetando(null);
        await cargar();
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo guardar la etiqueta.");
      } finally {
        setGuardando(false);
      }
    },
    [cargar, etiquetador, showNotice],
  );

  return (
    <div className={`dashboard ${light ? "light" : ""}`}>
      <aside>
        <Brand compact />
        <nav>
          <button
            className={activeSection === "overview" ? "active" : ""}
            onClick={() => setActiveSection("overview")}
          >
            <Icon name="dashboard" />
            <span>Panel general</span>
          </button>
          <button
            className={activeSection === "requests" ? "active" : ""}
            onClick={() => setActiveSection("requests")}
          >
            <Icon name="grid" />
            <span>Solicitudes</span>
            <b>{metricas.abiertas.length}</b>
          </button>
          <button
            className={activeSection === "etiquetado" ? "active" : ""}
            onClick={() => setActiveSection("etiquetado")}
          >
            <Icon name="check" />
            <span>Etiquetado</span>
            <b>{stats?.sin_etiquetar ?? 0}</b>
          </button>
          <button
            className={activeSection === "map" ? "active" : ""}
            onClick={() => setActiveSection("map")}
          >
            <Icon name="map" />
            <span>Mapa de OTBs</span>
          </button>
          <button
            className={activeSection === "crews" ? "active" : ""}
            onClick={() => setActiveSection("crews")}
          >
            <Icon name="users" />
            <span>Cuadrillas</span>
          </button>
          <button
            className={activeSection === "prueba" ? "active" : ""}
            onClick={() => setActiveSection("prueba")}
          >
            <Icon name="mic" />
            <span>Prueba del agente</span>
          </button>
          <button
            className={activeSection === "model" ? "active" : ""}
            onClick={() => {
              setActiveSection("model");
              setSubseccionModelo("resumen");
            }}
          >
            <Icon name="bolt" />
            <span>Modelo Agente</span>
          </button>
          {activeSection === "model" && (
            <Navar
              activa={subseccionModelo}
              onCambiar={(subseccion) => {
                setSubseccionModelo(subseccion);
                setActiveSection("model");
              }}
            />
          )}
        </nav>
        <div className="side-bottom">
          <button onClick={() => setUtilityPanel("settings")}>
            <Icon name="settings" />
            <span>Configuración</span>
          </button>
          <button onClick={() => setUtilityPanel("support")}>
            <Icon name="headset" />
            <span>Soporte técnico</span>
          </button>
          <button className="operator" onClick={() => setUtilityPanel("profile")}>
            <span>#3</span>
            <div>
              <b>Equipo # 3</b>
              <small>Etiquetador</small>
            </div>
            <i>•••</i>
          </button>
        </div>
      </aside>

      <div className="dash-content">
        <header>
          <div>
            <div className="eyebrow">SISTEMA INTELIGENTE · APRENDIZAJE SUPERVISADO + NLP</div>
            <h1>
              {SECTION_TITLES[activeSection][0]} <em>{SECTION_TITLES[activeSection][1]}</em>
            </h1>
            <p>
              Clasificación automática, explicación de predicciones y derivación operativa por OTB.
            </p>
          </div>
          <div className="dash-header-actions">
            <div className="live">
              <i /> {modelo ? `MODELO ${modelo.version} ACTIVO` : "SIN MODELO ENTRENADO"}
            </div>
            <button onClick={() => void cargar()} title="Recargar datos">
              <Icon name="clock" />
            </button>
            <button onClick={() => setLight(!light)} title="Cambiar tema">
              <Icon name={light ? "moon" : "sun"} />
            </button>
            <button className="kiosk-link" onClick={onKiosk}>
              VER KIOSCO <Icon name="arrow" size={17} />
            </button>
          </div>
        </header>

        <main>
          {error && (
            <div className="alert-banner error">
              <Icon name="bolt" size={16} />
              <span>{error}</span>
            </div>
          )}

          {activeSection === "overview" && (
            <section className="metric-grid">
              <article>
                <div>
                  <small>SOLICITUDES REGISTRADAS</small>
                  <h2>{stats?.total_solicitudes ?? solicitudes.length}</h2>
                  <span className="up">{stats?.etiquetadas ?? 0} etiquetadas</span>
                  <p>en la base de datos</p>
                </div>
              </article>
              <article>
                <div>
                  <small>F1 MACRO DEL MODELO</small>
                  <h2>
                    {modelo ? (modelo.f1_macro * 100).toFixed(1) : "—"}
                    <sup>%</sup>
                  </h2>
                  <span className="up">{modelo ? modelo.version : "sin modelo"}</span>
                  <p>conjunto de evaluación</p>
                </div>
                <div className="gauge">
                  <span>{modelo ? `${(modelo.f1_macro * 100).toFixed(1)}%` : "—"}</span>
                </div>
              </article>
              <article className="pending">
                <div>
                  <small>PENDIENTES DE ASIGNACIÓN</small>
                  <h2>{metricas.pendientes.length}</h2>
                  <span>{metricas.pendientesAlta.length} alta prioridad</span>
                </div>
                <div className="dept-bars">
                  <i style={{ width: "86%" }} />
                  <i style={{ width: "64%" }} />
                  <i style={{ width: "48%" }} />
                  <i style={{ width: "32%" }} />
                </div>
              </article>
              <article>
                <div>
                  <small>TIEMPO MEDIO DE CLASIFICACIÓN</small>
                  <h2>
                    {Math.round(metricas.latenciaMedia)}
                    <sup>ms</sup>
                  </h2>
                  <span className="up">
                    confianza media {metricas.confianzaMedia.toFixed(1)}%
                  </span>
                  <p>inferencia medida</p>
                </div>
                <div className="clock-ring">
                  <span>{(metricas.latenciaMedia / 1000).toFixed(3)}s</span>
                </div>
              </article>
            </section>
          )}

          {(activeSection === "overview" || activeSection === "requests") && (
            <section className="table-card">
              <div className="table-head">
                <div>
                  <h3>SOLICITUDES ENTRANTES</h3>
                  <p>Estado real registrado en la base de datos</p>
                </div>
                <div className="table-tools">
                  <label>
                    <Icon name="search" size={17} />
                    <input
                      placeholder="Buscar solicitud..."
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setPagina(1);
                      }}
                    />
                  </label>
                  {["Todas", "Alta", "Media", "Baja"].map((item) => (
                    <button
                      className={filter === item ? "active" : ""}
                      onClick={() => {
                        setFilter(item);
                        setPagina(1);
                      }}
                      key={item}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>SOLICITUD</th>
                      <th>CATEGORÍA</th>
                      <th>PRIORIDAD</th>
                      <th>CONFIANZA</th>
                      <th>ESTADO</th>
                      <th>ACCIÓN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cargando && filas.length === 0 && (
                      <tr>
                        <td colSpan={6} className="table-empty">
                          Cargando solicitudes desde el servidor…
                        </td>
                      </tr>
                    )}
                    {filas.map((solicitud) => (
                      <tr key={solicitud.id}>
                        <td>
                          <div className="request-id">
                            <b>{solicitud.ticket}</b>
                            <span>{relativeTime(solicitud.fecha)}</span>
                            {solicitud.origen === "kiosco" && (
                              <em className="kiosk-tag">KIOSCO</em>
                            )}
                          </div>
                          <p>{solicitud.texto}</p>
                          <small>
                            ⌖ {solicitud.otb} · {solicitud.zona}
                          </small>
                        </td>
                        <td>
                          <span className="category-dot" />
                          {categoriaDe(solicitud)}
                          {solicitud.etiquetada && <em className="kiosk-tag">✓</em>}
                        </td>
                        <td>
                          {prioridadDe(solicitud) ? (
                            <span className={`priority ${prioridadDe(solicitud)!.toLowerCase()}`}>
                              <i /> {prioridadDe(solicitud)}
                            </span>
                          ) : (
                            <span className="priority media">
                              <i /> —
                            </span>
                          )}
                        </td>
                        <td>
                          <b className="confidence-cell">
                            {solicitud.confianza !== null ? `${solicitud.confianza.toFixed(1)}%` : "—"}
                          </b>
                          <span className="mini-confidence">
                            <i style={{ width: `${solicitud.confianza ?? 0}%` }} />
                          </span>
                          {solicitud.requiere_revision && (
                            <em className="review-tag">REQUIERE REVISIÓN</em>
                          )}
                        </td>
                        <td>
                          <span className={`state ${solicitud.estado.toLowerCase().replace(" ", "-")}`}>
                            <i /> {solicitud.estado}
                          </span>
                        </td>
                        <td>
                          <div className="row-actions">
                            <button className="nlp-button" onClick={() => onInspect(solicitud)}>
                              VER NLP
                            </button>
                            <button className="label" onClick={() => abrirEtiqueta(solicitud)}>
                              {solicitud.etiquetada ? "CORREGIR ETIQUETA" : "CONFIRMAR / ETIQUETAR"}
                            </button>
                            <button
                              className="assign"
                              disabled={solicitud.estado !== "Sin asignar"}
                              onClick={() => void asignar(solicitud)}
                            >
                              {solicitud.estado === "Sin asignar" ? "ASIGNAR" : solicitud.estado}{" "}
                              <Icon name="chevron" size={15} />
                            </button>
                            <button
                              className="assign resolve"
                              disabled={solicitud.estado === "Resuelto"}
                              onClick={() => void resolver(solicitud)}
                            >
                              RESOLVER
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {!cargando && filas.length === 0 && (
                      <tr>
                        <td colSpan={6} className="table-empty">
                          No hay solicitudes que coincidan con el filtro aplicado.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="table-footer">
                <span>
                  Mostrando {filas.length} de {visible.length} solicitudes
                </span>
                <div>
                  <button onClick={() => setPagina(Math.max(1, paginaActual - 1))}>‹</button>
                  {Array.from({ length: totalPaginas }, (_, i) => i + 1)
                    .slice(0, 7)
                    .map((numero) => (
                      <button
                        className={paginaActual === numero ? "active" : ""}
                        onClick={() => setPagina(numero)}
                        key={numero}
                      >
                        {numero}
                      </button>
                    ))}
                  {totalPaginas > 7 && <span>… {totalPaginas}</span>}
                  <button onClick={() => setPagina(Math.min(totalPaginas, paginaActual + 1))}>
                    ›
                  </button>
                </div>
              </div>
            </section>
          )}

          {activeSection === "overview" && (
            <section className="analytics-grid">
              <article className="zone-chart">
                <div className="section-title">
                  <div>
                    <h3>DISTRIBUCIÓN POR OTB</h3>
                    <p>Reportes territoriales registrados en el sistema</p>
                  </div>
                </div>
                <div className="heat-body">
                  <div className="radar">
                    <span className="radar-ring r1" />
                    <span className="radar-ring r2" />
                    <span className="radar-ring r3" />
                    <span className="radar-axis a1" />
                    <span className="radar-axis a2" />
                    <span className="radar-axis a3" />
                    <div className="radar-shape" />
                  </div>
                  <div className="zone-list">
                    {cargaOtb.length > 0 ? (
                      cargaOtb.map((zone) => (
                        <div key={zone.name}>
                          <b>
                            <i style={{ background: zone.color }} />
                            {zone.name}
                          </b>
                          <span>{zone.count}</span>
                          <small>
                            <i style={{ width: zone.percent }} />
                          </small>
                        </div>
                      ))
                    ) : (
                      <p className="zone-empty">Aún no hay solicitudes territoriales registradas.</p>
                    )}
                  </div>
                </div>
              </article>
              <article className="model-card">
                <div className="section-title">
                  <div>
                    <h3>RENDIMIENTO DEL MODELO</h3>
                    <p>
                      {modelo
                        ? `${modelo.algoritmo} · ${modelo.version}`
                        : "Sin modelo entrenado"}
                    </p>
                  </div>
                  {modelo && (
                    <span className="stable">
                      <i /> {stats?.datos_suficientes ? "ESTABLE" : "PRELIMINAR"}
                    </span>
                  )}
                </div>
                {modelo ? (
                  <>
                    <div className="model-score">
                      <div className="score-ring">
                        <span>
                          {(modelo.f1_macro * 100).toFixed(1)}
                          <small>%</small>
                        </span>
                      </div>
                      <div>
                        <b>F1 MACRO</b>
                        <p>
                          {modelo.n_entrenamiento} casos de entrenamiento · {modelo.n_prueba} en
                          prueba fija
                        </p>
                      </div>
                    </div>
                    <div className="model-stats">
                      <div>
                        <span>PRECISIÓN</span>
                        <b>{(modelo.precision_macro * 100).toFixed(1)}%</b>
                        <i>
                          <em style={{ width: `${modelo.precision_macro * 100}%` }} />
                        </i>
                      </div>
                      <div>
                        <span>RECALL</span>
                        <b>{(modelo.recall_macro * 100).toFixed(1)}%</b>
                        <i>
                          <em style={{ width: `${modelo.recall_macro * 100}%` }} />
                        </i>
                      </div>
                      <div>
                        <span>ACCURACY</span>
                        <b>{(modelo.accuracy * 100).toFixed(1)}%</b>
                        <i>
                          <em style={{ width: `${modelo.accuracy * 100}%` }} />
                        </i>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="zone-empty">
                    Aún no hay un modelo entrenado. Ve a la sección Etiquetado y luego reentrena el
                    agente.
                  </p>
                )}
                <button className="model-link" onClick={() => setActiveSection("model")}>
                  VER DETALLE DEL MODELO <Icon name="arrow" size={16} />
                </button>
              </article>
            </section>
          )}

          {activeSection === "etiquetado" && (
            <EtiquetadoPage
              onNotice={showNotice}
              onInspect={onInspect}
              onBack={() => setActiveSection("overview")}
            />
          )}
          {activeSection === "map" && (
            <MapPage solicitudes={solicitudes} onInspect={onInspect} />
          )}
          {activeSection === "crews" && (
            <CrewsPage
              solicitudes={solicitudes}
              onAssign={(solicitud, cuadrilla) => {
                void asignarSolicitud(solicitud.id, cuadrilla).then(() => cargar());
              }}
              onNotice={showNotice}
            />
          )}
          {activeSection === "model" && (
            <ModelPage
              onNotice={showNotice}
              onDemo={solicitudes[0] ? () => onInspect(solicitudes[0]) : undefined}
              subseccion={subseccionModelo}
            />
          )}
          {activeSection === "prueba" && (
            <PruebaAgente onBack={() => setActiveSection("overview")} />
          )}
        </main>
      </div>

      {etiquetando && (
        <div className="inspector-backdrop" onMouseDown={() => setEtiquetando(null)}>
          <section className="utility-panel label-panel" onMouseDown={(e) => e.stopPropagation()}>
            <button className="utility-close" onClick={() => setEtiquetando(null)}>
              ×
            </button>
            <small>ETIQUETA CORRECTA · {etiquetando.ticket}</small>
            <h3>Confirmar o corregir la clasificación</h3>
            <p className="label-panel-text">{etiquetando.texto}</p>
            {etiquetando.categoria_predicha_nombre && (
              <p className="label-panel-pred">
                Predicción del modelo: <b>{etiquetando.categoria_predicha_nombre}</b> ·{" "}
                <b>{etiquetando.prioridad_predicha}</b> ({etiquetando.confianza?.toFixed(1) ?? "—"}%)
              </p>
            )}
            <label>
              <span>Categoría correcta</span>
              <select
                value={categoriaManual}
                onChange={(e) => setCategoriaManual(e.target.value)}
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
              <span>Prioridad</span>
              <div className="priority-picker">
                {(["ALTA", "MEDIA", "BAJA"] as Priority[]).map((nivel) => (
                  <button
                    className={`${nivel.toLowerCase()} ${prioridadManual === nivel ? "active" : ""}`}
                    onClick={() => setPrioridadManual(nivel)}
                    key={nivel}
                  >
                    {nivel}
                  </button>
                ))}
              </div>
            </label>
            <label>
              <span>Etiquetado por</span>
              <input value={etiquetador} onChange={(e) => setEtiquetador(e.target.value)} />
            </label>
            <button
              className="utility-action"
              disabled={!categoriaManual || guardando}
              onClick={() => void guardarEtiqueta(etiquetando, categoriaManual, prioridadManual)}
            >
              {guardando ? "GUARDANDO…" : "GUARDAR ETIQUETA"}
            </button>
          </section>
        </div>
      )}

      {notice && (
        <div className="admin-toast">
          <span>✓</span>
          {notice}
        </div>
      )}

      {utilityPanel && (
        <div className="utility-backdrop" onMouseDown={() => setUtilityPanel(null)}>
          <section className="utility-panel" onMouseDown={(event) => event.stopPropagation()}>
            <button className="utility-close" onClick={() => setUtilityPanel(null)}>
              ×
            </button>
            {utilityPanel === "settings" && (
              <>
                <Icon name="settings" size={30} />
                <small>CONFIGURACIÓN DEL SISTEMA</small>
                <h3>Preferencias operativas</h3>
                <p>
                  Versión activa del modelo: <b>{modelo?.version ?? "sin modelo"}</b>
                  <br />
                  Umbral de revisión humana: <b>confianza &lt; {salud?.umbral_confianza ?? "—"}%</b> o{" "}
                  <b>margen &lt; {salud?.umbral_margen ?? "—"}%</b>
                  <br />
                  Etiquetas registradas: <b>{salud?.n_etiquetas ?? stats?.etiquetadas ?? 0}</b>
                  <br />
                  Origen de datos: <b>PostgreSQL Local (backend FastAPI)</b>
                </p>
                <button
                  className="utility-action"
                  onClick={() => {
                    void cargar();
                    showNotice("Datos recargados desde el servidor");
                    setUtilityPanel(null);
                  }}
                >
                  RECARGAR DATOS
                </button>
              </>
            )}
            {utilityPanel === "support" && (
              <>
                <Icon name="headset" size={30} />
                <small>CENTRO DE SOPORTE</small>
                <h3>Estado del servicio</h3>
                <p>
                  Backend FastAPI:{" "}
                  <b className={salud?.estado === "ok" ? "online-text" : "offline-text"}>
                    {salud ? salud.estado : "sin respuesta"}
                  </b>
                  <br />
                  Base de datos:{" "}
                  <b className={salud?.base_datos === "conectada" ? "online-text" : "offline-text"}>
                    {salud?.base_datos ?? "sin verificar"}
                  </b>
                  <br />
                  Modelo activo: <b>{salud?.version_modelo ?? modelo?.version ?? "sin modelo"}</b>
                  <br />
                  Etiquetas registradas: <b>{salud?.n_etiquetas ?? 0}</b>
                  <br />
                  Clave de API: <b>{salud?.api_key_activa ? "requerida" : "no configurada"}</b>
                  <br />
                  Endpoint de la API: <b>/api → 127.0.0.1:8000</b>
                </p>
                <button
                  className="support-option"
                  onClick={() => {
                    void cargar();
                    showNotice("Estado del servicio verificado contra el backend");
                  }}
                >
                  Verificar conexión <Icon name="arrow" size={15} />
                </button>
                <button
                  className="support-option"
                  onClick={() => {
                    void generarInforme({ generado_por: "Equipo # 3" })
                      .then((respuesta) => {
                        showNotice(
                          `Informe #${respuesta.id} generado. Descárgalo en el Laboratorio de IA.`,
                        );
                        setUtilityPanel(null);
                        setActiveSection("model");
                      })
                      .catch((fallo) =>
                        showNotice(
                          fallo instanceof Error ? fallo.message : "No se pudo generar el informe.",
                        ),
                      );
                  }}
                >
                  Generar informe del agente <Icon name="arrow" size={15} />
                </button>
              </>
            )}
            {utilityPanel === "profile" && (
              <>
                <div className="profile-avatar">#3</div>
                <small>PERFIL DEL EQUIPO</small>
                <h3>Equipo # 3</h3>
                <p>
                  Rol: Etiquetado y entrenamiento
                  <br />
                  Etiquetas registradas:{" "}
                  {stats?.por_etiquetador.reduce((suma, p) => suma + p.total, 0) ?? 0}
                  <br />
                  Solicitudes gestionadas: {solicitudes.length}
                </p>
                <button
                  className="utility-action"
                  onClick={() => showNotice("Sesión verificada")}
                >
                  VER ACTIVIDAD
                </button>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
