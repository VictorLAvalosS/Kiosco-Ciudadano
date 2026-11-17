import { useCallback, useEffect, useState } from "react";
import type { FormatoInforme, Informe, InformeResumen } from "@/types";
import {
  descargarInforme,
  generarInforme,
  listarInformes,
  obtenerInforme,
} from "@/lib/api";
import { Icon } from "@/components/Icon";

/** Formatos de descarga disponibles con su etiqueta visible. */
const FORMATOS: { valor: FormatoInforme; etiqueta: string }[] = [
  { valor: "md", etiqueta: "MARKDOWN (.md)" },
  { valor: "json", etiqueta: "JSON (.json)" },
  { valor: "zip", etiqueta: "ZIP (con CSV)" },
];

/** Clase de estado para el semáforo del informe. */
function claseEstado(estado: string): string {
  if (estado === "completado") return "state resuelto";
  if (estado === "error") return "state en-proceso";
  return "state en-proceso";
}

/**
 * Tarjeta «Informe del agente» (Fase B5).
 *
 * Genera, desde la interfaz, el informe exhaustivo del backend (Markdown +
 * JSON + ZIP con los CSV de las matrices). Muestra el historial almacenado en
 * la base de datos, una vista previa del Markdown y permite descargarlo en los
 * tres formatos. Todos los valores provienen del informe real; nada se simula.
 */
export function InformeCard({ onNotice }: { onNotice: (message: string) => void }) {
  const [historial, setHistorial] = useState<InformeResumen[]>([]);
  const [seleccionado, setSeleccionado] = useState<Informe | null>(null);
  const [cargando, setCargando] = useState(true);
  const [generando, setGenerando] = useState(false);
  const [descargando, setDescargando] = useState<FormatoInforme | null>(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [error, setError] = useState("");

  /** Refresca el historial de informes guardados en la base de datos. */
  const cargarHistorial = useCallback(async () => {
    setCargando(true);
    try {
      setHistorial(await listarInformes());
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo cargar el historial de informes.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargarHistorial();
  }, [cargarHistorial]);

  /** Abre la vista previa de un informe (Markdown + JSON estructurado). */
  const ver = useCallback(async (id: number) => {
    setCargandoDetalle(true);
    setError("");
    try {
      setSeleccionado(await obtenerInforme(id));
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo abrir el informe.");
    } finally {
      setCargandoDetalle(false);
    }
  }, []);

  /** Genera un informe nuevo y abre automáticamente su vista previa. */
  const generar = useCallback(async () => {
    setGenerando(true);
    setError("");
    try {
      const respuesta = await generarInforme({});
      await cargarHistorial();
      await ver(respuesta.id);
      onNotice(`Informe #${respuesta.id} generado (estado: ${respuesta.estado}).`);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo generar el informe.");
    } finally {
      setGenerando(false);
    }
  }, [cargarHistorial, onNotice, ver]);

  /** Descarga el informe en el formato indicado como archivo local. */
  const descargar = useCallback(
    async (id: number, formato: FormatoInforme) => {
      setDescargando(formato);
      setError("");
      try {
        const blob = await descargarInforme(id, formato);
        const url = URL.createObjectURL(blob);
        const enlace = document.createElement("a");
        enlace.href = url;
        enlace.download = `informe_${id}.${formato}`;
        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();
        URL.revokeObjectURL(url);
        onNotice(`Informe #${id} descargado en formato ${formato.toUpperCase()}.`);
      } catch (fallo) {
        setError(fallo instanceof Error ? fallo.message : "No se pudo descargar el informe.");
      } finally {
        setDescargando(null);
      }
    },
    [onNotice],
  );

  return (
    <div className="versions-card informe-card">
      <div className="section-title">
        <div>
          <h3>INFORME DEL AGENTE</h3>
          <p>
            Documento exhaustivo generado desde la base de datos y el modelo activo: métricas,
            matrices, parámetros, eficiencia y ejemplos de proceso. Se guarda y queda versionado.
          </p>
        </div>
        <button onClick={() => void generar()} disabled={generando}>
          {generando ? "GENERANDO…" : "GENERAR INFORME"}
        </button>
      </div>

      {error && (
        <div className="alert-banner error">
          <Icon name="bolt" size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="informe-layout">
        <div className="informe-historial">
          <div className="subsection-title">HISTORIAL DE INFORMES</div>
          {cargando ? (
            <p className="zone-empty">Consultando los informes almacenados…</p>
          ) : historial.length === 0 ? (
            <p className="zone-empty">
              Todavía no se ha generado ningún informe. Pulsa <b>GENERAR INFORME</b> para crear el
              primero.
            </p>
          ) : (
            <div className="table-scroll">
              <table className="class-metrics">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>FECHA</th>
                    <th>VERSIÓN</th>
                    <th>ESTADO</th>
                    <th>ACCIÓN</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((informe) => (
                    <tr key={informe.id} className={seleccionado?.id === informe.id ? "informe-activo" : ""}>
                      <td>
                        <b>{informe.id}</b>
                      </td>
                      <td>{new Date(informe.fecha).toLocaleString("es-BO")}</td>
                      <td>{informe.version_modelo || "—"}</td>
                      <td>
                        <span className={claseEstado(informe.estado)} title={informe.error || undefined}>
                          <i /> {informe.estado.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <button
                          className="nlp-button"
                          disabled={cargandoDetalle}
                          onClick={() => void ver(informe.id)}
                        >
                          VER
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="informe-detalle">
          {seleccionado ? (
            <>
              <div className="subsection-title">
                INFORME #{seleccionado.id} · VERSIÓN {seleccionado.version_modelo || "—"}
              </div>
              <div className="informe-descargas">
                {FORMATOS.map((formato) => (
                  <button
                    key={formato.valor}
                    disabled={
                      descargando !== null || seleccionado.estado !== "completado"
                    }
                    onClick={() => void descargar(seleccionado.id, formato.valor)}
                  >
                    {descargando === formato.valor ? "DESCARGANDO…" : formato.etiqueta}
                  </button>
                ))}
              </div>
              {seleccionado.estado === "completado" ? (
                <pre className="informe-preview">{seleccionado.contenido_md}</pre>
              ) : (
                <p className="zone-empty">
                  El informe está en estado <b>{seleccionado.estado}</b>. Vuelve a consultarlo cuando
                  finalice la generación.
                </p>
              )}
            </>
          ) : (
            <p className="zone-empty">
              Selecciona un informe del historial (botón <b>VER</b>) para previsualizar su contenido y
              descargarlo en Markdown, JSON o ZIP.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
