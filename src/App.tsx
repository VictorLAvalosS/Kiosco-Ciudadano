import { useCallback, useEffect, useState } from "react";
import type { Prediccion, Solicitud } from "@/types";
import { ApiError, crearSolicitud } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { KioskHome } from "@/components/Kiosk";
import { Processing } from "@/components/Processing";
import { Result } from "@/components/Result";
import { Dashboard } from "@/components/Dashboard";
import { NLPInspector } from "@/components/NlpInspector";

type View = "kiosk" | "processing" | "result" | "dashboard";

/** Divide un texto en tokens simples para la animación (respaldo sin modelo). */
function tokensSimples(texto: string): string[] {
  return texto.split(/\s+/).filter(Boolean);
}

export default function App() {
  const [view, setView] = useState<View>("kiosk");
  const [current, setCurrent] = useState<Solicitud | null>(null);
  const [prediccion, setPrediccion] = useState<Prediccion | null>(null);
  const [pendingText, setPendingText] = useState("");
  const [animationDone, setAnimationDone] = useState(false);
  const [inspected, setInspected] = useState<Solicitud | null>(null);
  const [error, setError] = useState("");

  /** Envía la solicitud al backend, que la clasifica y la guarda en la base de datos. */
  const handleAnalyze = useCallback(async (text: string, otb: string) => {
    setError("");
    setPendingText(text);
    setCurrent(null);
    setPrediccion(null);
    setAnimationDone(false);
    setView("processing");

    try {
      const solicitud = await crearSolicitud({ texto: text, otb, origen: "kiosco" });
      setCurrent(solicitud);
      setPrediccion(solicitud.prediccion_detalle ?? null);
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "Ocurrió un error inesperado.");
      setView("kiosk");
    }
  }, []);

  // Solo se muestra el resultado cuando la animación y la respuesta del servidor terminan.
  useEffect(() => {
    if (view === "processing" && animationDone && current) {
      setView("result");
    }
  }, [view, animationDone, current]);

  const handleReset = useCallback(() => {
    setCurrent(null);
    setPrediccion(null);
    setError("");
    setView("kiosk");
  }, []);

  return (
    <>
      {view === "kiosk" && <KioskHome onAnalyze={handleAnalyze} error={error} />}

      {view === "processing" && (
        <Processing
          tokens={prediccion ? prediccion.tokens : tokensSimples(pendingText)}
          serverDone={current !== null}
          onDone={() => setAnimationDone(true)}
        />
      )}

      {view === "result" && current && (
        <Result
          solicitud={current}
          onReset={handleReset}
          onInspect={() => setInspected(current)}
        />
      )}

      {view === "dashboard" && (
        <Dashboard onKiosk={() => setView("kiosk")} onInspect={(solicitud) => setInspected(solicitud)} />
      )}

      {view !== "dashboard" && (
        <button className="admin-peek" onClick={() => setView("dashboard")}>
          <Icon name="dashboard" size={18} /> PANEL ADMIN
        </button>
      )}

      {inspected && <NLPInspector solicitud={inspected} onClose={() => setInspected(null)} />}
    </>
  );
}
