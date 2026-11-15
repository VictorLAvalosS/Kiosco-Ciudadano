import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { Brand, StatusPill } from "@/components/shared";

const STAGES = [
  "Normalizando el texto recibido",
  "Eliminando palabras vacías (stopwords)",
  "Vectorizando con TF-IDF (unigramas y bigramas)",
  "Aplicando el clasificador supervisado",
  "Calculando prioridad y derivación",
];

/**
 * Pantalla de progreso. Los tokens mostrados provienen del pipeline real
 * (`/api/predecir`); la animación solo recorre visualmente esa lista.
 *
 * La animación visual dura ~2 s, pero la pantalla no se cierra hasta que el
 * servidor responde (`serverDone`). Esto evita que la pantalla se quede "en
 * blanco" cuando la primera llamada tarda en deserializar el modelo.
 */
export function Processing({
  tokens,
  serverDone,
  onDone,
}: {
  tokens: string[];
  serverDone: boolean;
  onDone: () => void;
}) {
  const [progress, setProgress] = useState(6);

  useEffect(() => {
    setProgress(6);
    const interval = setInterval(() => setProgress((value) => Math.min(value + 6, 100)), 90);
    return () => clearInterval(interval);
  }, []);

  // Cuando la animación llega al 100 % y el servidor ya respondió, cerramos.
  useEffect(() => {
    if (progress >= 100 && serverDone) {
      onDone();
    }
  }, [progress, serverDone, onDone]);

  const stageIndex = Math.min(STAGES.length - 1, Math.floor((progress / 100) * STAGES.length));
  const highlightLimit = Math.ceil((progress / 100) * tokens.length);
  const esperandoServidor = progress >= 100 && !serverDone;

  return (
    <div className="processing-screen">
      <div className="processing-grid" />
      <header>
        <Brand />
        <StatusPill />
      </header>
      <main>
        <div className="neural-orb">
          <i />
          <i />
          <i />
          <div>
            <Icon name="bolt" size={30} />
          </div>
        </div>
        <div className="eyebrow centered">
          <span>02</span> ANÁLISIS SEMÁNTICO EN CURSO
        </div>
        <h2>
          Comprendiendo tu <em>solicitud</em>
        </h2>
        <p>
          {esperandoServidor
            ? "El agente ya procesó el texto. Conectando con la base de datos para guardar tu solicitud…"
            : "Nuestro agente está identificando el contexto, la ubicación y el nivel de urgencia."}
        </p>
        <div className="token-card">
          <div className="scan-line" />
          <div className="token-label">
            TEXTO TOKENIZADO{" "}
            <span>{progress < 100 ? "● PROCESANDO" : esperandoServidor ? "● LISTO · ESPERANDO ALMACENAMIENTO" : "● COMPLETADO"}</span>
          </div>
          <div className="tokens">
            {tokens.length === 0 && <span>Procesando…</span>}
            {tokens.map((token, index) => (
              <span key={`${token}-${index}`} className={index < highlightLimit ? "keyword" : ""}>
                {token}
              </span>
            ))}
          </div>
        </div>
        <div className="model-progress">
          <div
            className="progress-ring"
            style={{ "--progress": `${progress * 3.6}deg` } as React.CSSProperties}
          >
            <span>
              {progress}
              <small>%</small>
            </span>
          </div>
          <div>
            <b>{STAGES[stageIndex].toUpperCase()}</b>
            {STAGES.map((stage, index) => (
              <span key={stage} className={index > stageIndex ? "pending" : ""}>
                <i /> {stage}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
