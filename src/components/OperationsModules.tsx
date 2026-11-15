import type { Solicitud } from "@/types";
import { CREWS } from "@/lib/catalogos";
import { Icon } from "@/components/Icon";

/** Posición determinista de un marcador en el mapa (según el id del registro). */
function pinPosition(id: number, index: number) {
  let hash = 7;
  const texto = String(id);
  for (let i = 0; i < texto.length; i += 1) hash = (hash * 31 + texto.charCodeAt(i)) % 9973;
  const left = 12 + ((hash * 13 + index * 41) % 74);
  const top = 14 + ((hash * 7 + index * 29) % 66);
  return { left: `${left}%`, top: `${top}%` };
}

/** Prioridad real que muestra el marcador (predicha por el modelo o etiquetada). */
function prioridadDe(solicitud: Solicitud): string {
  return solicitud.etiqueta?.prioridad ?? solicitud.prioridad_predicha ?? "MEDIA";
}

export function MapPage({
  solicitudes,
  onInspect,
}: {
  solicitudes: Solicitud[];
  onInspect: (solicitud: Solicitud) => void;
}) {
  const activas = solicitudes.filter((solicitud) => solicitud.estado !== "Resuelto");
  const cuadrillasEnRuta = CREWS.filter(
    (crew) => crew.status === "En ruta" || crew.status === "En operación",
  );

  const porOtb = new Map<string, number>();
  solicitudes.forEach((solicitud) => {
    const otb = solicitud.otb || "Sin OTB";
    porOtb.set(otb, (porOtb.get(otb) ?? 0) + 1);
  });

  return (
    <section className="module-page">
      <div className="module-heading">
        <div>
          <span>MÓDULO OPERATIVO</span>
          <h2>Mapa territorial de OTBs</h2>
          <p>Ubicación de reportes, límites vecinales y cuadrillas desplegadas</p>
        </div>
        <button
          onClick={() => solicitudes[0] && onInspect(solicitudes[0])}
          disabled={solicitudes.length === 0}
        >
          INSPECCIONAR SOLICITUD ACTIVA
        </button>
      </div>
      <div className="operations-map">
        <div className="map-grid" />
        {solicitudes.slice(0, 8).map((solicitud, index) => (
          <button
            className={`map-pin ${prioridadDe(solicitud).toLowerCase()}`}
            style={pinPosition(solicitud.id, index)}
            onClick={() => onInspect(solicitud)}
            key={solicitud.id}
          >
            <i />
            {solicitud.ticket}
            <small>
              {solicitud.otb.replace("OTB ", "")} · {prioridadDe(solicitud)}
            </small>
          </button>
        ))}
        <div className="map-legend">
          <b>CAPAS DEL MAPA</b>
          <label>
            <input type="checkbox" defaultChecked /> Solicitudes
          </label>
          <label>
            <input type="checkbox" defaultChecked /> Cuadrillas
          </label>
          <label>
            <input type="checkbox" defaultChecked /> Límites OTB
          </label>
        </div>
        <div className="map-summary">
          <b>{activas.length}</b>
          <span>REPORTES ACTIVOS</span>
          <b>{cuadrillasEnRuta.length}</b>
          <span>CUADRILLAS EN RUTA</span>
        </div>
        <div className="map-otb-list">
          <b>CARGA POR OTB</b>
          {[...porOtb.entries()].length > 0 ? (
            [...porOtb.entries()].slice(0, 5).map(([nombre, total]) => (
              <div key={nombre}>
                <span>{nombre.replace("OTB ", "")}</span>
                <b>{total}</b>
              </div>
            ))
          ) : (
            <p className="zone-empty">Aún no hay solicitudes registradas.</p>
          )}
        </div>
      </div>
    </section>
  );
}

/** Cuadrilla que tiene asignada una solicitud de su categoría (según el estado). */
function tareaActual(claveCategoria: string | null, solicitudes: Solicitud[]) {
  if (!claveCategoria) return undefined;
  return solicitudes.find(
    (solicitud) =>
      solicitud.categoria_predicha_clave === claveCategoria && solicitud.estado === "Asignado",
  );
}

/** Primera solicitud sin asignar de la categoría de la cuadrilla. */
function pendienteDeCuadrilla(claveCategoria: string, solicitudes: Solicitud[]) {
  return solicitudes.find(
    (solicitud) =>
      solicitud.estado === "Sin asignar" && solicitud.categoria_predicha_clave === claveCategoria,
  );
}

export function CrewsPage({
  solicitudes,
  onAssign,
  onNotice,
}: {
  solicitudes: Solicitud[];
  onAssign: (solicitud: Solicitud, cuadrilla: string) => void;
  onNotice: (message: string) => void;
}) {
  return (
    <section className="module-page">
      <div className="module-heading">
        <div>
          <span>MÓDULO OPERATIVO</span>
          <h2>Gestión de cuadrillas</h2>
          <p>Disponibilidad y carga operativa por equipo especializado</p>
        </div>
        <button onClick={() => onNotice("Datos operativos actualizados correctamente")}>
          ACTUALIZAR DATOS
        </button>
      </div>
      <div className="crew-grid">
        {CREWS.map((crew, index) => {
          const actual = tareaActual(crew.categoria, solicitudes);
          const pendiente = pendienteDeCuadrilla(crew.categoria, solicitudes);
          return (
            <article key={crew.id}>
              <div className="crew-icon">
                <Icon name={crew.icon} />
              </div>
              <span className={`crew-status s${index % 4}`}>{crew.status}</span>
              <h3>{crew.name}</h3>
              <p>{crew.specialty}</p>
              <div>
                <span>
                  PERSONAL <b>{crew.load}</b>
                </span>
                <span>
                  BASE <b>{crew.base}</b>
                </span>
              </div>
              <div className="crew-task">
                {actual ? (
                  <>
                    <small>ATENDIENDO</small>
                    <b>
                      {actual.ticket} · {prioridadDe(actual)}
                    </b>
                  </>
                ) : (
                  <>
                    <small>SIN ASIGNACIÓN ACTIVA</small>
                    <b>{pendiente ? `${pendiente.ticket} en espera` : "Sin pendientes"}</b>
                  </>
                )}
              </div>
              <button
                disabled={!pendiente}
                onClick={() => {
                  if (!pendiente) return;
                  onAssign(pendiente, crew.name);
                  onNotice(`${pendiente.ticket} asignada a la cuadrilla ${crew.name}`);
                }}
              >
                {pendiente ? "ASIGNAR SOLICITUD" : "SIN PENDIENTES"} <Icon name="arrow" size={15} />
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
