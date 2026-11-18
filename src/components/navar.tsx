/** Subsecciones disponibles dentro del panel Modelo Agente. */
export type SubseccionModelo = "resumen" | "analisis";

interface NavarProps {
  activa: SubseccionModelo;
  onCambiar: (subseccion: SubseccionModelo) => void;
}

/** Submenú lateral que aparece al abrir Modelo Agente en el panel administrativo. */
export function Navar({ activa, onCambiar }: NavarProps) {
  return (
    <div className="model-sidebar-subnav" aria-label="Secciones del modelo agente">
      <button
        type="button"
        aria-current={activa === "resumen" ? "page" : undefined}
        className={activa === "resumen" ? "active" : ""}
        onClick={() => onCambiar("resumen")}
      >
        <small>01</small>
        <span>Resumen y evaluación</span>
      </button>
      <button
        type="button"
        aria-current={activa === "analisis" ? "page" : undefined}
        className={activa === "analisis" ? "active" : ""}
        onClick={() => onCambiar("analisis")}
      >
        <small>02</small>
        <span>Análisis y configuración</span>
      </button>
    </div>
  );
}
