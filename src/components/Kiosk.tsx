import { useEffect, useRef, useState } from "react";
import type { IconName, Prediccion } from "@/types";
import { predecir } from "@/lib/api";
import { OTB_OPTIONS, extraerOtb } from "@/lib/catalogos";
import { Icon } from "@/components/Icon";
import { Brand, StatusPill } from "@/components/shared";

const quickReports: { name: string; icon: IconName; text: string }[] = [
  { name: "Baches", icon: "road", text: "Hay un bache profundo en la avenida principal que dificulta el tránsito." },
  { name: "Agua potable", icon: "droplet", text: "Hay una tubería rota en la Av. Blanco Galindo que está inundando la calle." },
  { name: "Alumbrado", icon: "lightbulb", text: "Tres luminarias no funcionan en la plaza del Distrito 4 y la zona queda oscura." },
  { name: "Basura", icon: "trash", text: "Hay residuos acumulados desde hace varios días en la esquina del mercado." },
  { name: "Áreas verdes", icon: "leaf", text: "Un árbol caído bloquea parcialmente la acera del parque principal." },
  { name: "Seguridad", icon: "shield", text: "Se reportan robos frecuentes en horas de la noche en la zona del barrio." },
];

/**
 * Vista previa del análisis. Consulta el endpoint real `/api/predecir`
 * (no guarda nada) con un retardo para no saturar el backend en cada tecla.
 */
function LivePreview({ text }: { text: string }) {
  const [prediccion, setPrediccion] = useState<Prediccion | null>(null);
  const [estado, setEstado] = useState<
    "inactivo" | "cargando" | "listo" | "sin-modelo" | "error"
  >("inactivo");

  useEffect(() => {
    if (text.trim().length < 12) {
      setPrediccion(null);
      setEstado("inactivo");
      return;
    }

    const controlador = new AbortController();
    let vigente = true;
    setEstado("cargando");
    const temporizador = setTimeout(async () => {
      try {
        const resultado = await predecir(text, controlador.signal);
        if (!vigente) return;
        setPrediccion(resultado);
        setEstado("listo");
      } catch (fallo) {
        if (!vigente) return;
        const status =
          typeof fallo === "object" && fallo !== null && "status" in fallo
            ? (fallo as { status: number }).status
            : 0;
        setPrediccion(null);
        if (status === 409) {
          setEstado("sin-modelo");
        } else if (status >= 500 || status === 0) {
          setEstado("error");
        } else {
          setEstado("inactivo");
        }
      }
    }, 600);

    return () => {
      vigente = false;
      clearTimeout(temporizador);
      controlador.abort();
    };
  }, [text]);

  if (estado === "inactivo") {
    return (
      <div className="live-preview empty">
        <Icon name="bolt" size={16} />
        El análisis previo aparecerá mientras escribes…
      </div>
    );
  }

  if (estado === "sin-modelo") {
    return (
      <div className="live-preview empty">
        <Icon name="bolt" size={16} />
        El agente aún no ha sido entrenado. Ve al panel de IA y entrena una versión.
      </div>
    );
  }

  if (estado === "error") {
    return (
      <div className="live-preview empty">
        <Icon name="bolt" size={16} />
        No se pudo conectar con el servidor de IA. Asegúrate de que la API esté
        corriendo (<code>npm run api</code>).
      </div>
    );
  }

  if (estado === "cargando" || !prediccion) {
    return (
      <div className="live-preview">
        <div className="live-preview-head">
          <span>
            <i /> ANALIZANDO CON EL MODELO ACTIVO…
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="live-preview">
      <div className="live-preview-head">
        <span>
          <i /> ANÁLISIS PREVIO EN TIEMPO REAL · {prediccion.version_modelo}
        </span>
        <b>{prediccion.latencia_ms} ms</b>
      </div>
      <div className="live-preview-body">
        <div className="preview-category">
          <span className={`preview-icon cat-${prediccion.categoria}`}>
            <Icon name={prediccion.icono as IconName} size={20} />
          </span>
          <div>
            <small>CATEGORÍA PROBABLE</small>
            <b>{prediccion.categoria_nombre}</b>
          </div>
        </div>
        <div className="preview-metrics">
          <span className={`priority ${prediccion.prioridad.toLowerCase()}`}>
            <i /> {prediccion.prioridad}
          </span>
          <span className="preview-confidence">
            CONFIANZA <b>{prediccion.confianza.toFixed(1)}%</b>
          </span>
        </div>
      </div>
      {prediccion.contribuciones.length > 0 && (
        <div className="preview-keywords">
          {prediccion.contribuciones.slice(0, 5).map((aporte) => (
            <span key={aporte.termino}>
              {aporte.termino} <small>{aporte.contribucion.toFixed(2)}</small>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function KioskHome({
  onAnalyze,
  error,
}: {
  onAnalyze: (text: string, otb: string) => void;
  error: string;
}) {
  const [text, setText] = useState("");
  const [otb, setOtb] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState("");
  const recognitionRef = useRef<{
    stop: () => void;
    abort: () => void;
  } | null>(null);

  /**
   * Dictado por voz. Usa la Web Speech API con reconocimiento continuo y
   * resultados intermedios para que el ciudadano vea el texto en tiempo real.
   * Cuando en el discurso se menciona una OTB, se selecciona automáticamente.
   */
  const dictate = () => {
    // Si ya está escuchando, al presionar de nuevo se detiene.
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setListening(true);
      setVoiceNotice(
        "Tu navegador no soporta dictado por voz. Usa Chrome o Edge, o escribe la solicitud manualmente.",
      );
      // Demostración del flujo sin micrófono: incluye una OTB para que se
      // auto-seleccione y el usuario vea cómo funciona.
      const ejemplo =
        "Tenemos un problema de alumbrado público en la avenida Bolívar de la OTB Ceibo";
      setText(ejemplo);
      const otbDetectada = extraerOtb(ejemplo);
      if (otbDetectada) {
        setOtb(otbDetectada);
        setVoiceNotice(
          `Ejemplo cargado. Se detectó automáticamente la OTB: ${otbDetectada}.`,
        );
      }
      setTimeout(() => setListening(false), 1200);
      return;
    }

    const recognition = new (SpeechRecognition as new () => {
      lang: string;
      continuous: boolean;
      interimResults: boolean;
      onstart: () => void;
      onend: () => void;
      onerror: (event: { error?: string }) => void;
      onresult: (event: {
        resultIndex: number;
        results: ArrayLike<ArrayLike<{ transcript: string }>> & { length: number };
      }) => void;
      start: () => void;
      stop: () => void;
      abort: () => void;
    })();

    recognition.lang = "es-BO";
    recognition.continuous = true;
    recognition.interimResults = true;

    // Texto acumulado (los resultados finales se concatenan).
    let textoFinal = text;

    recognition.onstart = () => {
      setListening(true);
      setVoiceNotice("Escuchando… habla con calma. Menciona la OTB si quieres que se seleccione sola.");
    };

    recognition.onerror = (event) => {
      setListening(false);
      setVoiceNotice(
        event.error === "not-allowed" || event.error === "service-not-allowed"
          ? "No se pudo acceder al micrófono. Autoriza el permiso o escribe la solicitud."
          : "No se pudo reconocer la voz. Intenta de nuevo o escribe la solicitud.",
      );
    };

    recognition.onend = () => {
      setListening(false);
      setVoiceNotice((prev) =>
        prev && prev.includes("Escuchando") ? "" : prev,
      );
    };

    recognition.onresult = (event) => {
      let textoInterino = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const resultado = event.results[i];
        const transcript = resultado[0].transcript;
        // `isFinal` no está en el tipo mínimo; se detecta si el índice no cambió.
        const esFinal = (resultado as unknown as { isFinal?: boolean }).isFinal;
        if (esFinal) {
          textoFinal = textoFinal ? `${textoFinal} ${transcript}`.trim() : transcript;
        } else {
          textoInterino += transcript;
        }
      }
      const textoCompleto = textoInterino ? `${textoFinal} ${textoInterino}`.trim() : textoFinal;
      setText(textoCompleto);

      // Detección automática de la OTB en lo que se va diciendo.
      const otbDetectada = extraerOtb(textoCompleto);
      if (otbDetectada && otbDetectada !== otb) {
        setOtb(otbDetectada);
        setVoiceNotice(`OTB detectada automáticamente: ${otbDetectada}.`);
      }
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch {
      setVoiceNotice("El reconocimiento ya está activo. Espera un momento.");
    }
  };

  // Limpia el reconocimiento al desmontar.
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return (
    <div className="kiosk-shell">
      <header className="kiosk-header">
        <Brand />
        <StatusPill />
      </header>
      <main className="kiosk-main">
        <div className="eyebrow">
          <span>01</span> NUEVA SOLICITUD CIUDADANA
        </div>
        <h1>
          ¿Cómo podemos
          <br />
          <em>ayudarte hoy?</em>
        </h1>
        <p className="lead">
          Describe lo que sucede con tus propias palabras.
          <br />
          El sistema analizará el texto, clasificará el problema y lo derivará al área responsable.
        </p>

        <div className={`report-input ${listening ? "is-listening" : ""}`}>
          <div className="territory-selector">
            <div>
              <Icon name="map" size={19} />
              <span>
                <b>ORGANIZACIÓN TERRITORIAL DE BASE</b>
                <small>Selecciona la OTB donde ocurre el problema</small>
              </span>
            </div>
            <select value={otb} onChange={(event) => setOtb(event.target.value)}>
              <option value="">Seleccionar OTB...</option>
              {OTB_OPTIONS.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div className="input-label">
            <span>DESCRIBE TU SOLICITUD</span>
            <span>{text.length} / 500</span>
          </div>
          <textarea
            value={text}
            maxLength={500}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ej. Hay una tubería rota en la Av. Blanco Galindo que está inundando la calle..."
          />
          <button className="voice-button" onClick={dictate}>
            <span className="mic-orbit">
              <Icon name="mic" size={27} />
            </span>
            <span>
              <b>{listening ? "ESCUCHANDO..." : "DICTADO POR VOZ"}</b>
              <small>{listening ? "Habla ahora" : "Toca para comenzar"}</small>
            </span>
            <span className="wave">
              <i />
              <i />
              <i />
              <i />
              <i />
            </span>
          </button>
          {voiceNotice && <p className="voice-notice">{voiceNotice}</p>}
        </div>

        <LivePreview text={text} />

        <div className="quick-head">
          <span>O SELECCIONA UN REPORTE FRECUENTE</span>
          <i />
        </div>
        <div className="quick-grid wide">
          {quickReports.map((item) => (
            <button key={item.name} onClick={() => setText(item.text)}>
              <span>
                <Icon name={item.icon} size={25} />
              </span>
              {item.name}
              <Icon name="chevron" size={16} />
            </button>
          ))}
        </div>

        {error && (
          <div className="kiosk-error">
            <Icon name="bolt" size={16} /> {error}
          </div>
        )}

        <button
          className="analyze-button"
          disabled={!text.trim()}
          onClick={() => {
            // Si el usuario no seleccionó OTB, se intenta detectar del texto.
            const otbFinal = otb || extraerOtb(text);
            if (!otbFinal) {
              setVoiceNotice(
                "No se detectó la OTB. Selecciónala en el campo de arriba o menciónala en la descripción.",
              );
              return;
            }
            setVoiceNotice("");
            onAnalyze(text.trim(), otbFinal);
          }}
        >
          <span className="ai-spark">
            <Icon name="bolt" size={25} />
          </span>
          <span>
            <b>ANALIZAR Y ENVIAR</b>
            <small>SOLICITUD CON INTELIGENCIA ARTIFICIAL</small>
          </span>
          <Icon name="arrow" size={26} />
        </button>
        <div className="privacy-note">
          <span className="shield-check">✓</span> Tus datos están protegidos y serán utilizados
          únicamente para gestionar tu solicitud.
        </div>
      </main>
      <footer>
        <span>TECNOLOGÍA AL SERVICIO DE LA CIUDADANÍA</span>
        <span>
          ES · ACCESIBILIDAD <b>Aa</b>
        </span>
      </footer>
    </div>
  );
}
