import { useMemo, useState } from "react";
import type { IconName, Solicitud } from "@/types";
import { Icon } from "@/components/Icon";
import { Brand, StatusPill } from "@/components/shared";

const PRIORITY_META: Record<string, { level: string; sla: string; dots: number }> = {
  ALTA: { level: "NIVEL 3", sla: "Requiere atención en menos de 24 h", dots: 3 },
  MEDIA: { level: "NIVEL 2", sla: "Requiere atención en menos de 48 h", dots: 2 },
  BAJA: { level: "NIVEL 1", sla: "Requiere atención en menos de 72 h", dots: 1 },
};

/** Construye una matriz determinista tipo QR a partir del código de ticket. */
function qrMatrix(value: string, size = 21): boolean[][] {
  let seed = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    seed ^= value.charCodeAt(i);
    seed = Math.imul(seed, 16777619);
  }
  const matrix: boolean[][] = Array.from({ length: size }, () => new Array(size).fill(false));

  const finder = (row: number, col: number) => {
    for (let r = -1; r <= 7; r += 1) {
      for (let c = -1; c <= 7; c += 1) {
        const rr = row + r;
        const cc = col + c;
        if (rr < 0 || cc < 0 || rr >= size || cc >= size) continue;
        const border = r === 0 || r === 6 || c === 0 || c === 6;
        const core = r >= 2 && r <= 4 && c >= 2 && c <= 4;
        matrix[rr][cc] = (r >= 0 && r <= 6 && c >= 0 && c <= 6 && border) || core;
      }
    }
  };
  finder(0, 0);
  finder(0, size - 7);
  finder(size - 7, 0);

  let state = seed || 1;
  const reserved = (row: number, col: number) =>
    (row <= 7 && col <= 7) || (row <= 7 && col >= size - 8) || (row >= size - 8 && col <= 7);

  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      if (reserved(row, col)) continue;
      state = (state * 1103515245 + 12345) & 0x7fffffff;
      matrix[row][col] = ((state >> 9) & 1) === 1;
    }
  }
  return matrix;
}

export function Result({
  solicitud,
  onReset,
  onInspect,
}: {
  solicitud: Solicitud;
  onReset: () => void;
  onInspect: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const prioridad = solicitud.prioridad_predicha ?? "MEDIA";
  const meta = PRIORITY_META[prioridad];
  const confianza = solicitud.confianza ?? 0;
  const categoria = solicitud.categoria_predicha_nombre ?? "Sin clasificar";
  const departamento = solicitud.categoria_predicha_departamento ?? "Pendiente de derivación";
  const icono = (solicitud.categoria_predicha_icono ?? "grid") as IconName;

  const matrix = useMemo(() => qrMatrix(solicitud.ticket), [solicitud.ticket]);

  const copy = () => {
    navigator.clipboard?.writeText(solicitud.ticket);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div className="result-screen">
      <header>
        <Brand />
        <StatusPill />
      </header>
      <main>
        <div className="success-icon">
          <Icon name="check" size={42} />
        </div>
        <div className="eyebrow centered">
          <span>03</span> SOLICITUD REGISTRADA
        </div>
        <h2>
          Tu reporte fue <em>clasificado con éxito</em>
        </h2>
        <p className="lead">La unidad responsable ha sido notificada automáticamente.</p>
        <section className="result-card">
          <div className="assigned">
            <small>DEPARTAMENTO ASIGNADO POR IA</small>
            <div className="department-icon">
              <Icon name={icono} size={29} />
            </div>
            <h3>{departamento.toUpperCase()}</h3>
            <div className="route-line">
              <span /> DERIVACIÓN AUTOMÁTICA COMPLETADA <span />
            </div>
          </div>
          <div className="result-metrics">
            <div>
              <small>NIVEL DE PRIORIDAD</small>
              <b>
                <span className="traffic">
                  {[1, 2, 3].map((dot) => (
                    <i key={dot} className={dot <= meta.dots ? "on" : ""} />
                  ))}
                </span>{" "}
                URGENCIA {prioridad} <em>{meta.level}</em>
              </b>
              <p>{meta.sla}</p>
            </div>
            <div>
              <small>CONFIANZA DEL ALGORITMO</small>
              <b className="confidence-number">{confianza.toFixed(1)}%</b>
              <div className="confidence-bar">
                <i style={{ width: `${confianza}%` }} />
              </div>
              <p>
                {confianza >= 85
                  ? "Predicción de alta precisión"
                  : confianza >= 65
                    ? "Predicción con revisión recomendada"
                    : "Predicción de baja certeza · revisión humana"}
              </p>
            </div>
          </div>
          <div className="ticket-area">
            <div>
              <small>CÓDIGO DE SEGUIMIENTO</small>
              <h4>{solicitud.ticket}</h4>
              <div className="ticket-otb">
                <Icon name="map" size={14} /> {solicitud.otb}
              </div>
              <p>
                Guarda este código para consultar
                <br />
                el estado de tu solicitud.
              </p>
              <button onClick={copy}>
                <Icon name="copy" size={16} /> {copied ? "CÓDIGO COPIADO" : "COPIAR CÓDIGO"}
              </button>
            </div>
            <div className="ticket-qr" aria-label={`Código QR de seguimiento ${solicitud.ticket}`}>
              {matrix.flatMap((row, rowIndex) =>
                row.map((on, colIndex) => (
                  <i key={`${rowIndex}-${colIndex}`} className={on ? "on" : ""} />
                )),
              )}
            </div>
          </div>
        </section>
        <div className="result-meta">
          <span>
            CATEGORÍA PREDICHA <b>{categoria}</b>
          </span>
          <span>
            MODELO <b>{solicitud.version_modelo ?? "—"}</b>
          </span>
          <span>
            LATENCIA DE INFERENCIA <b>{solicitud.latencia_ms ?? 0} ms</b>
          </span>
        </div>
        <div className="result-actions">
          <button className="print" onClick={onInspect}>
            <Icon name="bolt" /> VER TRAZABILIDAD NLP
          </button>
          <button onClick={() => window.print()}>
            <Icon name="printer" /> IMPRIMIR COMPROBANTE
          </button>
        </div>
        <div className="result-nav">
          <button onClick={onReset}>
            NUEVO REPORTE <Icon name="arrow" />
          </button>
        </div>
        <div className="notification-note">
          <span>✓</span>
          <p>
            <b>Notificación enviada</b>
            <br />
            El equipo operativo recibió tu solicitud y ubicación.
          </p>
        </div>
      </main>
    </div>
  );
}
