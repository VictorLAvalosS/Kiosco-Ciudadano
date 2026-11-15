import { useEffect, useState } from "react";
import type { IconName, Modelo, Prediccion, Solicitud } from "@/types";
import { modeloActivo, predecir } from "@/lib/api";
import { Icon } from "@/components/Icon";

const STEP_NAMES = [
  "Entrada",
  "Tokenización",
  "Vectorización",
  "Contexto",
  "Clasificación",
  "Decisión",
];

/** Normalización simple para la vista (minúsculas y sin tildes). */
function normalizarSimple(valor: string): string {
  return valor
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function NLPInspector({
  solicitud,
  onClose,
}: {
  solicitud: Solicitud;
  onClose: () => void;
}) {
  const [step, setStep] = useState(1);
  const [prediccion, setPrediccion] = useState<Prediccion | null>(null);
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [error, setError] = useState("");

  // Ejecuta el pipeline real sin guardar nada y consulta la versión activa.
  useEffect(() => {
    let vigente = true;

    (async () => {
      try {
        const [resultado, activo] = await Promise.all([
          predecir(solicitud.texto),
          modeloActivo().catch(() => null),
        ]);
        if (!vigente) return;
        setPrediccion(resultado);
        setModelo(activo);
      } catch (fallo) {
        if (!vigente) return;
        setError(fallo instanceof Error ? fallo.message : "No se pudo ejecutar el pipeline.");
      }
    })();

    return () => {
      vigente = false;
    };
  }, [solicitud.texto]);

  const tokensSet = new Set(prediccion?.tokens ?? []);
  const maxTfidf = prediccion
    ? Math.max(1e-9, ...prediccion.contribuciones.map((c) => c.tfidf))
    : 1;

  return (
    <div className="inspector-backdrop" onMouseDown={onClose}>
      <aside className="nlp-inspector" onMouseDown={(event) => event.stopPropagation()}>
        <header className="inspector-head">
          <div>
            <span>TRAZABILIDAD DEL ALGORITMO</span>
            <h2>
              Inspector NLP <em>{solicitud.ticket}</em>
            </h2>
            <p>Área: Aprendizaje Supervisado · Subárea: Procesamiento de Lenguaje Natural</p>
            <small className="inspector-otb">
              {solicitud.otb} · {solicitud.zona}
            </small>
          </div>
          <button onClick={onClose} aria-label="Cerrar inspector">
            ×
          </button>
        </header>

        <div className="pipeline-nav">
          {STEP_NAMES.map((name, index) => (
            <button
              className={step === index + 1 ? "active" : step > index + 1 ? "done" : ""}
              onClick={() => setStep(index + 1)}
              key={name}
            >
              <span>{step > index + 1 ? "✓" : index + 1}</span>
              <small>PASO {index + 1}</small>
              <b>{name}</b>
            </button>
          ))}
        </div>

        <div className="inspector-content">
          {error && (
            <section className="explain-step">
              <div className="teacher-note">
                <b>NO SE PUDO EJECUTAR EL PIPELINE</b>
                <p>{error}</p>
              </div>
            </section>
          )}

          {!error && !prediccion && (
            <section className="explain-step">
              <div className="teacher-note">
                <b>EJECUTANDO EL PIPELINE REAL…</b>
                <p>Consultando el modelo activo almacenado en la base de datos.</p>
              </div>
            </section>
          )}

          {prediccion && (
            <>
              {step === 1 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>01</span>
                    <div>
                      <h3>Captura y normalización del texto</h3>
                      <p>
                        El sistema recibe lenguaje natural libre y prepara una versión uniforme para
                        el clasificador.
                      </p>
                    </div>
                  </div>
                  <div className="input-comparison">
                    <article>
                      <small>ENTRADA ORIGINAL DEL CIUDADANO</small>
                      <blockquote>“{prediccion.texto}”</blockquote>
                      <span>{prediccion.texto.length} caracteres</span>
                    </article>
                    <div className="transform-arrow">→</div>
                    <article>
                      <small>TEXTO NORMALIZADO</small>
                      <blockquote>{prediccion.texto_normalizado}</blockquote>
                      <span>Minúsculas · Sin tildes · Sin signos · UTF-8 normalizado</span>
                    </article>
                  </div>
                  <div className="inspector-stats">
                    <div>
                      <small>CARACTERES</small>
                      <b>{prediccion.texto.length}</b>
                    </div>
                    <div>
                      <small>PALABRAS (TOKENS)</small>
                      <b>{prediccion.tokens_originales.length}</b>
                    </div>
                    <div>
                      <small>PALABRAS VACÍAS</small>
                      <b>{prediccion.stopwords}</b>
                    </div>
                    <div>
                      <small>TOKENS ÚTILES</small>
                      <b>{prediccion.tokens.length}</b>
                    </div>
                    <div>
                      <small>N-GRAMAS QUE APORTAN</small>
                      <b>{prediccion.contribuciones.length}</b>
                    </div>
                  </div>
                  <div className="teacher-note">
                    <b>¿POR QUÉ SE HACE?</b>
                    <p>
                      “TUBERÍA”, “Tubería” y “tuberia” deben representar la misma característica. La
                      normalización reduce ruido sin cambiar el significado del reclamo.
                    </p>
                  </div>
                </section>
              )}

              {step === 2 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>02</span>
                    <div>
                      <h3>Tokenización y eliminación de stopwords</h3>
                      <p>
                        La oración se divide en unidades y se descartan los conectores que aportan
                        poca intención.
                      </p>
                    </div>
                  </div>
                  <div className="token-explainer">
                    {prediccion.tokens_originales.map((palabra, index) => {
                      const util = tokensSet.has(normalizarSimple(palabra));
                      return (
                        <button className={util ? "strong" : "stop"} key={`${palabra}-${index}`}>
                          <b>{palabra}</b>
                          <small>{util ? "TOKEN ÚTIL" : "STOPWORD DESCARTADA"}</small>
                        </button>
                      );
                    })}
                  </div>
                  <div className="token-legend">
                    <span>
                      <i className="strong" /> Token conservado para el clasificador
                    </span>
                    <span>
                      <i className="stop" /> Stopword eliminada
                    </span>
                  </div>
                  <div className="code-line">
                    <span>tokens_limpios</span> = [
                    {prediccion.tokens.map((token) => `"${token}"`).join(", ")}]
                  </div>
                </section>
              )}

              {step === 3 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>03</span>
                    <div>
                      <h3>Vectorización TF-IDF (unigramas y bigramas)</h3>
                      <p>
                        Cada palabra y cada pareja de palabras se transforma en un peso numérico
                        según su frecuencia e importancia en el corpus de entrenamiento.
                      </p>
                    </div>
                  </div>
                  {prediccion.contribuciones.length > 0 ? (
                    <div className="vector-grid">
                      {prediccion.contribuciones.map((aporte) => (
                        <article key={aporte.termino}>
                          <div>
                            <b>{aporte.termino}</b>
                            <span>{aporte.tfidf.toFixed(3)}</span>
                          </div>
                          <div className="vector-bar">
                            <i style={{ width: `${(aporte.tfidf / maxTfidf) * 100}%` }} />
                          </div>
                          <code>tf-idf = {aporte.tfidf.toFixed(4)}</code>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="teacher-note">
                      <b>SIN TÉRMINOS INFLUYENTES</b>
                      <p>
                        El vocabulario del modelo no reconoce términos de este texto con peso
                        positivo para la clase predicha.
                      </p>
                    </div>
                  )}
                  <div className="teacher-note">
                    <b>CONCEPTO CLAVE</b>
                    <p>
                      TF-IDF pondera cada término por su frecuencia en el documento (TF) y la
                      penaliza si aparece en muchos documentos (IDF). Los bigramas permiten capturar
                      expresiones como “tubería rota”.
                    </p>
                  </div>
                </section>
              )}

              {step === 4 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>04</span>
                    <div>
                      <h3>Contexto territorial y trazabilidad del registro</h3>
                      <p>
                        Además del texto, cada solicitud aporta metadatos reales almacenados en la
                        base de datos que acompañan la derivación.
                      </p>
                    </div>
                  </div>
                  <div className="context-row">
                    <div>
                      <small>OTB SELECCIONADA</small>
                      <b>
                        <Icon name="map" size={14} /> {solicitud.otb}
                      </b>
                    </div>
                    <div>
                      <small>ZONA / DISTRITO</small>
                      <b>{solicitud.zona}</b>
                    </div>
                    <div>
                      <small>TIPO DE REGISTRO</small>
                      <b>
                        {solicitud.origen === "kiosco"
                          ? "Kiosco ciudadano"
                          : solicitud.origen === "importado"
                            ? "Importado (CSV)"
                            : "Panel administrativo"}
                      </b>
                    </div>
                  </div>
                  <div className="context-row">
                    <div>
                      <small>CATEGORÍA ASIGNADA POR EL MODELO</small>
                      <b>
                        <Icon name={prediccion.icono as IconName} size={14} />{" "}
                        {prediccion.categoria_nombre}
                      </b>
                    </div>
                    <div>
                      <small>DEPARTAMENTO DESTINO</small>
                      <b>{prediccion.departamento}</b>
                    </div>
                    <div>
                      <small>FECHA DE REGISTRO</small>
                      <b>{new Date(solicitud.fecha).toLocaleString("es-BO")}</b>
                    </div>
                  </div>
                </section>
              )}

              {step === 5 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>05</span>
                    <div>
                      <h3>Clasificación supervisada multiclase</h3>
                      <p>
                        El vector se evalúa con el modelo activo, entrenado con las etiquetas reales
                        guardadas en la base de datos.
                      </p>
                    </div>
                  </div>
                  <div className="supervised-flow">
                    <article>
                      <small>DATOS DE ENTRENAMIENTO</small>
                      <b>{modelo ? modelo.n_entrenamiento.toLocaleString("es-BO") : "—"}</b>
                      <p>solicitudes etiquetadas</p>
                    </article>
                    <span>→</span>
                    <article>
                      <small>MODELO</small>
                      <b>{prediccion.algoritmo}</b>
                      <p>versión {prediccion.version_modelo}</p>
                    </article>
                    <span>→</span>
                    <article>
                      <small>F1 MACRO</small>
                      <b>{modelo ? `${(modelo.f1_macro * 100).toFixed(1)}%` : "—"}</b>
                      <p>conjunto de prueba fijo</p>
                    </article>
                  </div>
                  <div className="class-probabilities">
                    {prediccion.probabilidades.map((item) => {
                      const gana = item.clase === prediccion.categoria;
                      return (
                        <div className={gana ? "winner" : ""} key={item.clase}>
                          <span>
                            {modelo?.metricas_por_clase?.[item.clase] ? item.clase : item.clase}
                          </span>
                          <i>
                            <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
                          </i>
                          <b>{(item.probabilidad * 100).toFixed(1)}%</b>
                          {gana && <small>CLASE GANADORA</small>}
                        </div>
                      );
                    })}
                  </div>
                  <div className="subsection-title">RANKING DE PRIORIDAD PREDICHA</div>
                  <div className="class-probabilities">
                    {prediccion.probabilidades_prioridad.map((item) => (
                      <div className={item.clase === prediccion.prioridad ? "winner" : ""} key={item.clase}>
                        <span>{item.clase}</span>
                        <i>
                          <em style={{ width: `${Math.max(item.probabilidad * 100, 2)}%` }} />
                        </i>
                        <b>{(item.probabilidad * 100).toFixed(1)}%</b>
                      </div>
                    ))}
                  </div>
                  <div className="model-formula">
                    ŷ = argmax P(clase | vector de características) →{" "}
                    <b>{prediccion.categoria_nombre}</b>
                  </div>
                </section>
              )}

              {step === 6 && (
                <section className="explain-step">
                  <div className="step-heading">
                    <span>06</span>
                    <div>
                      <h3>Decisión explicable y derivación</h3>
                      <p>
                        El sistema combina categoría, urgencia, ubicación y confianza para producir
                        una acción auditable.
                      </p>
                    </div>
                  </div>
                  <div className="decision-card">
                    <div className="decision-check">✓</div>
                    <small>RESULTADO FINAL DEL PIPELINE</small>
                    <h3>{prediccion.categoria_nombre}</h3>
                    <div>
                      <span>
                        PRIORIDAD{" "}
                        <b className={prediccion.prioridad.toLowerCase()}>
                          {prediccion.prioridad}
                        </b>
                      </span>
                      <span>
                        CONFIANZA <b>{prediccion.confianza.toFixed(1)}%</b>
                      </span>
                      <span>
                        MARGEN <b>{prediccion.margen.toFixed(1)}%</b>
                      </span>
                      <span>
                        OTB <b>{solicitud.otb.replace("OTB ", "")}</b>
                      </span>
                    </div>
                  </div>
                  <div className="feature-contribution">
                    <div className="subsection-title">
                      CONTRIBUCIÓN DE CARACTERÍSTICAS A LA DECISIÓN (COEFICIENTE × TF-IDF)
                    </div>
                    {prediccion.contribuciones.length > 0 ? (
                      prediccion.contribuciones.slice(0, 6).map((aporte) => (
                        <div className="feature-row" key={aporte.termino}>
                          <span>{aporte.termino}</span>
                          <i>
                            <em
                              style={{
                                width: `${Math.min(100, Math.max(2, aporte.contribucion * 100))}%`,
                              }}
                            />
                          </i>
                          <b>{aporte.contribucion.toFixed(3)}</b>
                          <small>tf-idf {aporte.tfidf.toFixed(3)}</small>
                        </div>
                      ))
                    ) : (
                      <p className="zone-empty">
                        El modelo no expone coeficientes para esta arquitectura.
                      </p>
                    )}
                  </div>
                  <div className="audit-row">
                    <span>TIEMPO TOTAL DE INFERENCIA</span>
                    <b>{prediccion.latencia_ms} ms</b>
                    <span>VERSIÓN DEL MODELO</span>
                    <b>{prediccion.version_modelo}</b>
                    <span>REVISIÓN HUMANA</span>
                    <b>{prediccion.confianza < 70 ? "Requerida" : "Disponible"}</b>
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        <footer className="inspector-footer">
          <button disabled={step === 1} onClick={() => setStep(step - 1)}>
            ← PASO ANTERIOR
          </button>
          <div>
            {STEP_NAMES.map((_, index) => (
              <i className={step === index + 1 ? "active" : ""} key={index} />
            ))}
          </div>
          {step < STEP_NAMES.length ? (
            <button className="next" onClick={() => setStep(step + 1)}>
              SIGUIENTE PASO →
            </button>
          ) : (
            <button className="next" onClick={onClose}>
              FINALIZAR EXPLICACIÓN ✓
            </button>
          )}
        </footer>
      </aside>
    </div>
  );
}
