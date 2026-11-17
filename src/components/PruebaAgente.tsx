import { useCallback, useMemo, useState } from "react";
import type { IconName, Prediccion, TrazaAgente } from "@/types";
import { predecir } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { EcuacionLista } from "@/components/Ecuacion";

/** Ejemplos de prueba rápida para la defensa (texto libre del ciudadano). */
const EJEMPLOS = [
  "el foco de la esquina lleva tres noches quemado",
  "hay basura acumulada frente al mercado",
  "fuga de agua potable en la avenida principal",
  "el alcantarillado está rebalsando y huele mal",
];

/** Metadatos de cada una de las 11 etapas reales de la traza (Fase A1). */
interface PasoTraza {
  numero: number;
  titulo: string;
  resumen: string;
  /** Números de ecuación (Ec.) que explican este paso. */
  ecuaciones: number[];
}

const PASOS: PasoTraza[] = [
  {
    numero: 1,
    titulo: "Texto original",
    resumen: "El sistema recibe la solicitud en lenguaje natural libre, tal como la escribe el ciudadano.",
    ecuaciones: [],
  },
  {
    numero: 2,
    titulo: "Normalización",
    resumen: "Se pasa a minúsculas, se quitan tildes y signos: así “TUBERÍA”, “Tubería” y “tuberia” representan lo mismo.",
    ecuaciones: [],
  },
  {
    numero: 3,
    titulo: "Tokenización",
    resumen: "El texto normalizado se divide en unidades mínimas (tokens) que el clasificador puede procesar.",
    ecuaciones: [],
  },
  {
    numero: 4,
    titulo: "Eliminación de stopwords",
    resumen: "Se descartan los conectores y palabras vacías que aportan poca intención al reclamo.",
    ecuaciones: [],
  },
  {
    numero: 5,
    titulo: "N-gramas",
    resumen: "El analizador del vectorizador genera unigramas y bigramas reales (palabras y parejas de palabras).",
    ecuaciones: [1],
  },
  {
    numero: 6,
    titulo: "Pesos TF-IDF",
    resumen: "Cada término recibe un peso según su frecuencia en la solicitud y su rareza en el corpus de entrenamiento.",
    ecuaciones: [1, 2, 3],
  },
  {
    numero: 7,
    titulo: "Puntaje de decisión por clase",
    resumen: "Se calcula s_c(x) = w_c·x + b_c para cada una de las 8 categorías y se ordenan de mayor a menor.",
    ecuaciones: [4, 5, 19],
  },
  {
    numero: 8,
    titulo: "Probabilidades calibradas",
    resumen: "Los puntajes se transforman en probabilidades que suman 100 % mediante calibración y normalización.",
    ecuaciones: [6, 7, 20],
  },
  {
    numero: 9,
    titulo: "Margen de decisión",
    resumen: "Diferencia entre la clase más probable y la segunda: un margen pequeño indica indecisión del modelo.",
    ecuaciones: [8],
  },
  {
    numero: 10,
    titulo: "Decisión y umbrales",
    resumen: "Se compara la confianza y el margen con los umbrales; si no los superan, el caso pasa a revisión humana.",
    ecuaciones: [9],
  },
  {
    numero: 11,
    titulo: "Clasificación de prioridad",
    resumen: "El mismo pipeline se aplica a un segundo clasificador que estima ALTA / MEDIA / BAJA.",
    ecuaciones: [4, 7, 20],
  },
];

/** Barras horizontales reutilizadas para puntajes y probabilidades. */
function Barras({ filas }: { filas: { etiqueta: string; valor: number; nota?: string }[] }) {
  const maximo = Math.max(1e-9, ...filas.map((fila) => Math.abs(fila.valor)));
  return (
    <div className="traza-bars">
      {filas.map((fila) => (
        <div key={fila.etiqueta}>
          <span>{fila.etiqueta}</span>
          <i>
            <em style={{ width: `${Math.min(100, Math.max(3, (Math.abs(fila.valor) / maximo) * 100))}%` }} />
          </i>
          <b>{fila.valor.toFixed(2)}</b>
          {fila.nota && <small>{fila.nota}</small>}
        </div>
      ))}
    </div>
  );
}

/** Contenido de una etapa concreta de la traza (datos reales del modelo activo). */
function ContenidoPaso({ paso, traza }: { paso: number; traza: TrazaAgente }) {
  if (paso === 1) {
    return (
      <div className="teaching-block">
        <blockquote className="traza-quote">“{traza.texto_original}”</blockquote>
        <div className="inspector-stats">
          <div>
            <small>CARACTERES</small>
            <b>{traza.texto_original.length}</b>
          </div>
          <div>
            <small>PALABRAS</small>
            <b>{traza.tokens.length}</b>
          </div>
        </div>
      </div>
    );
  }

  if (paso === 2) {
    return (
      <div className="input-comparison">
        <article>
          <small>ENTRADA ORIGINAL</small>
          <blockquote>“{traza.texto_original}”</blockquote>
          <span>{traza.texto_original.length} caracteres</span>
        </article>
        <div className="transform-arrow">→</div>
        <article>
          <small>TEXTO NORMALIZADO</small>
          <blockquote>{traza.texto_normalizado || "—"}</blockquote>
          <span>Minúsculas · Sin tildes · Sin signos</span>
        </article>
      </div>
    );
  }

  if (paso === 3) {
    return (
      <div className="teaching-block">
        <div className="token-explainer">
          {traza.tokens.length > 0 ? (
            traza.tokens.map((token, indice) => (
              <button className="strong" key={`${token}-${indice}`}>
                <b>{token}</b>
                <small>TOKEN</small>
              </button>
            ))
          ) : (
            <p className="zone-empty">No se generaron tokens para este texto.</p>
          )}
        </div>
        <div className="code-line">
          <span>tokens</span> = [{traza.tokens.map((token) => `"${token}"`).join(", ")}]
        </div>
      </div>
    );
  }

  if (paso === 4) {
    return (
      <div className="teaching-block">
        <div className="subsection-title">TOKENS QUE SE CONSERVAN PARA EL CLASIFICADOR</div>
        <div className="token-explainer">
          {traza.tokens_sin_stopwords.length > 0 ? (
            traza.tokens_sin_stopwords.map((token, indice) => (
              <button className="strong" key={`${token}-${indice}`}>
                <b>{token}</b>
                <small>ÚTIL</small>
              </button>
            ))
          ) : (
            <p className="zone-empty">Todos los términos fueron stopwords.</p>
          )}
        </div>
        <div className="subsection-title">STOPWORDS ELIMINADAS</div>
        <div className="token-explainer">
          {traza.stopwords_eliminadas.length > 0 ? (
            traza.stopwords_eliminadas.map((token) => (
              <button className="stop" key={token}>
                <b>{token}</b>
                <small>DESCARTADA</small>
              </button>
            ))
          ) : (
            <p className="zone-empty">No se eliminó ningún término.</p>
          )}
        </div>
      </div>
    );
  }

  if (paso === 5) {
    return (
      <div className="teaching-block">
        <div className="token-explainer">
          {traza.n_gramas.map((ngrama, indice) => (
            <button className="strong" key={`${ngrama}-${indice}`}>
              <b>{ngrama}</b>
              <small>{ngrama.includes(" ") ? "BIGRAMA" : "UNIGRAMA"}</small>
            </button>
          ))}
        </div>
        <p className="zone-empty">
          Total de n-gramas generados: <b>{traza.n_gramas.length}</b>. La Ecuación 1 define cómo se
          cuenta cada término dentro del documento.
        </p>
      </div>
    );
  }

  if (paso === 6) {
    return (
      <div className="teaching-block">
        <table className="traza-table">
          <thead>
            <tr>
              <th>TÉRMINO</th>
              <th>tf</th>
              <th>idf</th>
              <th>tf-idf</th>
            </tr>
          </thead>
          <tbody>
            {traza.terminos_tfidf.map((termino) => (
              <tr key={termino.termino}>
                <td>{termino.termino}</td>
                <td>{termino.tf}</td>
                <td>{termino.idf.toFixed(3)}</td>
                <td>
                  <b>{termino.tfidf.toFixed(3)}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="zone-empty">
          Valores reales leídos del vectorizador TF-IDF del modelo activo (Ecuaciones 1, 2 y 3).
        </p>
      </div>
    );
  }

  if (paso === 7) {
    return (
      <Barras
        filas={traza.puntajes_categoria.map((puntaje) => ({
          etiqueta: puntaje.clase,
          valor: puntaje.puntaje,
        }))}
      />
    );
  }

  if (paso === 8) {
    return (
      <div className="teaching-block">
        <div className="class-probabilities">
          {traza.probabilidades_categoria.map((item) => (
            <div className={item.clase === traza.decision.categoria ? "winner" : ""} key={item.clase}>
              <span>{item.clase}</span>
              <i>
                <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
              </i>
              <b>{(item.probabilidad * 100).toFixed(1)}%</b>
            </div>
          ))}
        </div>
        <div className="model-formula">
          P(c | x) = exp(s_c) / Σ exp(s_c′) · suma de probabilidades = 100 %
        </div>
      </div>
    );
  }

  if (paso === 9) {
    return (
      <div className="inspector-stats">
        <div>
          <small>CLASE TOP-1</small>
          <b>{traza.decision.categoria}</b>
        </div>
        <div>
          <small>CONFIANZA</small>
          <b>{traza.confianza_categoria.toFixed(1)}%</b>
        </div>
        <div>
          <small>MARGEN (top-1 − top-2)</small>
          <b>{traza.margen_categoria.toFixed(1)}%</b>
        </div>
      </div>
    );
  }

  if (paso === 10) {
    const decision = traza.decision;
    return (
      <div className="teaching-block">
        <div className="traza-umbrales">
          <div className={decision.cumple_confianza ? "ok" : "warn"}>
            <span>CONFIANZA</span>
            <b>{decision.confianza.toFixed(1)}%</b>
            <small>
              umbral ≥ {decision.umbral_confianza}% ·{" "}
              {decision.cumple_confianza ? "CUMPLE" : "NO CUMPLE"}
            </small>
          </div>
          <div className={decision.cumple_margen ? "ok" : "warn"}>
            <span>MARGEN</span>
            <b>{decision.margen.toFixed(1)}%</b>
            <small>
              umbral ≥ {decision.umbral_margen}% · {decision.cumple_margen ? "CUMPLE" : "NO CUMPLE"}
            </small>
          </div>
        </div>
        <div className={`decision-card ${decision.resultado === "automatica" ? "auto" : "revision"}`}>
          <div className="decision-check">{decision.resultado === "automatica" ? "✓" : "!"}</div>
          <small>RESULTADO DE LA REGLA DE DECISIÓN</small>
          <h3>
            {decision.resultado === "automatica"
              ? "Clasificación automática aceptada"
              : "Enviada a revisión humana"}
          </h3>
          <div>
            <span>
              CATEGORÍA <b>{decision.categoria}</b>
            </span>
            <span>
              PRIORIDAD <b className={decision.prioridad.toLowerCase()}>{decision.prioridad}</b>
            </span>
          </div>
        </div>
      </div>
    );
  }

  // Paso 11: resumen equivalente del clasificador de prioridad.
  return (
    <div className="teaching-block">
      <div className="inspector-stats">
        <div>
          <small>PRIORIDAD PREDICHA</small>
          <b>{traza.prioridad.clase}</b>
        </div>
        <div>
          <small>CONFIANZA</small>
          <b>{traza.prioridad.confianza.toFixed(1)}%</b>
        </div>
        <div>
          <small>MARGEN</small>
          <b>{traza.prioridad.margen.toFixed(1)}%</b>
        </div>
      </div>
      <div className="class-probabilities">
        {traza.prioridad.probabilidades.map((item) => (
          <div className={item.clase === traza.prioridad.clase ? "winner" : ""} key={item.clase}>
            <span>{item.clase}</span>
            <i>
              <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
            </i>
            <b>{(item.probabilidad * 100).toFixed(1)}%</b>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Pestaña "Prueba del agente": ejecuta el pipeline NLP real (endpoint
 * /api/predecir) y muestra la traza de las 11 etapas con datos del modelo activo,
 * el diagrama del flujo y las ecuaciones que explican cada paso.
 */
export function PruebaAgente({ onBack }: { onBack: () => void }) {
  const [texto, setTexto] = useState("");
  const [resultado, setResultado] = useState<Prediccion | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [paso, setPaso] = useState(1);

  /** Ejecuta el pipeline NLP real (endpoint /api/predecir, sin guardar nada). */
  const clasificar = useCallback(async (entrada: string) => {
    const limpio = entrada.trim();
    if (limpio.length < 5) {
      setError("Escribe una solicitud de al menos 5 caracteres.");
      return;
    }
    setCargando(true);
    setError("");
    setResultado(null);
    setPaso(1);
    try {
      const prediccion = await predecir(limpio);
      setResultado(prediccion);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo ejecutar el clasificador.");
    } finally {
      setCargando(false);
    }
  }, []);

  const traza = resultado?.traza ?? null;
  const maxContribucion = resultado
    ? Math.max(1e-9, ...resultado.contribuciones.map((c) => Math.abs(c.contribucion)))
    : 1;

  const pasoActual = useMemo(() => PASOS[paso - 1], [paso]);

  return (
    <section className="module-page prueba-page">
      <div className="module-heading">
        <div>
          <span>PRUEBA DEL AGENTE EN VIVO · TRAZA COMPLETA</span>
          <h2>Escribe una solicitud y observa las 11 etapas de la inferencia</h2>
          <p>
            Usa el modelo activo almacenado en la base de datos. No se guarda ninguna solicitud: solo
            se muestra la traza, las probabilidades, las ecuaciones y la decisión final.
          </p>
        </div>
        <div className="heading-actions">
          <button onClick={onBack}>
            <Icon name="arrow" size={16} /> VOLVER AL PANEL
          </button>
        </div>
      </div>

      <article className="prueba-input-card">
        <label>
          <span>SOLICITUD CIUDADANA (LENGUAJE NATURAL)</span>
          <textarea
            value={texto}
            rows={3}
            maxLength={700}
            placeholder="Ej.: el foco de la esquina lleva tres noches quemado"
            onChange={(event) => setTexto(event.target.value)}
          />
        </label>
        <div className="prueba-actions">
          <div className="prueba-ejemplos">
            {EJEMPLOS.map((ejemplo) => (
              <button key={ejemplo} onClick={() => setTexto(ejemplo)} type="button">
                {ejemplo}
              </button>
            ))}
          </div>
          <button
            className="utility-action"
            disabled={cargando}
            onClick={() => void clasificar(texto)}
          >
            {cargando ? "CLASIFICANDO…" : "CLASIFICAR AHORA"}
          </button>
        </div>
      </article>

      {error && (
        <div className="alert-banner error">
          <Icon name="bolt" size={16} />
          <span>{error}</span>
        </div>
      )}

      {resultado && (
        <>
          <div className={`alert-banner ${resultado.requiere_revision ? "warn" : "ok"}`}>
            <Icon name={resultado.requiere_revision ? "bolt" : "check"} size={16} />
            <span>
              {resultado.requiere_revision ? (
                <>
                  <b>Requiere revisión humana.</b> La confianza ({resultado.confianza.toFixed(1)}%) o
                  el margen ({resultado.margen.toFixed(1)}%) quedan por debajo de los umbrales
                  (confianza ≥ {resultado.umbral_confianza}% y margen ≥ {resultado.umbral_margen}%).
                </>
              ) : (
                <>
                  <b>Predicción aceptada.</b> Confianza {resultado.confianza.toFixed(1)}% y margen{" "}
                  {resultado.margen.toFixed(1)}% por encima de los umbrales de revisión.
                </>
              )}
            </span>
          </div>

          <article className="prueba-verdict traza-verdict">
            <small>DECISIÓN DEL MODELO</small>
            <div className="department-icon">
              <Icon name={(resultado.icono as IconName) ?? "grid"} size={26} />
            </div>
            <h3>{resultado.categoria_nombre}</h3>
            <p className="prueba-departamento">{resultado.departamento}</p>
            <div className="prueba-badges">
              <span className={`priority ${resultado.prioridad.toLowerCase()}`}>
                <i /> {resultado.prioridad}
              </span>
              <span className="prueba-badge">CONFIANZA {resultado.confianza.toFixed(1)}%</span>
              <span className="prueba-badge">MARGEN {resultado.margen.toFixed(1)}%</span>
            </div>
            <p className="prueba-meta">
              Modelo <b>{resultado.version_modelo}</b> · {resultado.algoritmo} ·{" "}
              {resultado.latencia_ms} ms
            </p>
          </article>

          {/* Diagrama del flujo real de la inferencia (macro-etapas). */}
          <div className="architecture-flow traza-flow">
            {[
              "Texto ciudadano",
              "Normalización",
              "Tokens + stopwords",
              "TF-IDF (1-2 gramas)",
              "Puntaje y probabilidad",
              "Umbrales y decisión",
            ].map((item, index) => (
              <div key={item}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <b>{item}</b>
                {index < 5 && <i>→</i>}
              </div>
            ))}
          </div>

          {traza ? (
            <article className="traza-card">
              <div className="traza-nav">
                {PASOS.map((item) => (
                  <button
                    className={paso === item.numero ? "active" : paso > item.numero ? "done" : ""}
                    onClick={() => setPaso(item.numero)}
                    key={item.numero}
                  >
                    <span>{paso > item.numero ? "✓" : item.numero}</span>
                    <b>{item.titulo}</b>
                  </button>
                ))}
              </div>

              <div className="traza-content">
                <div className="step-heading">
                  <span>{String(pasoActual.numero).padStart(2, "0")}</span>
                  <div>
                    <h3>
                      {pasoActual.titulo}
                      <em className="traza-contador">ETAPA {pasoActual.numero} DE 11</em>
                    </h3>
                    <p>{pasoActual.resumen}</p>
                  </div>
                </div>

                <ContenidoPaso paso={paso} traza={traza} />

                <EcuacionLista numeros={pasoActual.ecuaciones} />

                <div className="traza-footer">
                  <button disabled={paso === 1} onClick={() => setPaso(paso - 1)}>
                    ← ETAPA ANTERIOR
                  </button>
                  <div className="traza-dots">
                    {PASOS.map((item) => (
                      <i className={paso === item.numero ? "active" : ""} key={item.numero} />
                    ))}
                  </div>
                  <button
                    className="next"
                    disabled={paso === 11}
                    onClick={() => setPaso(paso + 1)}
                  >
                    ETAPA SIGUIENTE →
                  </button>
                </div>
              </div>
            </article>
          ) : (
            <div className="alert-banner warn">
              <Icon name="bolt" size={16} />
              <span>
                La traza detallada no está disponible en esta respuesta. Se muestran las
                probabilidades del modelo activo.
              </span>
            </div>
          )}

          <div className="prueba-result-grid">
            <article>
              <small>PRIORIDAD</small>
              <div className="class-probabilities">
                {resultado.probabilidades_prioridad.map((item) => (
                  <div className={item.clase === resultado.prioridad ? "winner" : ""} key={item.clase}>
                    <span>{item.clase}</span>
                    <i>
                      <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
                    </i>
                    <b>{(item.probabilidad * 100).toFixed(1)}%</b>
                  </div>
                ))}
              </div>
            </article>
            <article>
              <small>PROBABILIDAD DE LAS 8 CATEGORÍAS</small>
              <div className="class-probabilities">
                {resultado.probabilidades.map((item) => (
                  <div className={item.clase === resultado.categoria ? "winner" : ""} key={item.clase}>
                    <span>{item.clase}</span>
                    <i>
                      <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
                    </i>
                    <b>{(item.probabilidad * 100).toFixed(1)}%</b>
                  </div>
                ))}
              </div>
            </article>
          </div>

          <article className="prueba-terms">
            <small>TÉRMINOS QUE MÁS PESARON EN LA DECISIÓN (COEFICIENTE × TF-IDF)</small>
            {resultado.contribuciones.length > 0 ? (
              <div className="feature-contribution">
                {resultado.contribuciones.slice(0, 8).map((aporte) => (
                  <div className="feature-row" key={aporte.termino}>
                    <span>{aporte.termino}</span>
                    <i>
                      <em
                        style={{
                          width: `${Math.min(100, Math.max(4, (Math.abs(aporte.contribucion) / maxContribucion) * 100))}%`,
                        }}
                      />
                    </i>
                    <b>{aporte.contribucion.toFixed(3)}</b>
                    <small>tf-idf {aporte.tfidf.toFixed(3)}</small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="zone-empty">
                El vocabulario del modelo no reconoce términos de esta solicitud con peso positivo
                para la clase predicha.
              </p>
            )}
          </article>
        </>
      )}
    </section>
  );
}
