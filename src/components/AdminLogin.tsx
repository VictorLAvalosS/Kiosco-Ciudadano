import { useState } from "react";
import type { FormEvent } from "react";
import { Icon } from "@/components/Icon";

export const CLAVE_SESION = "kiosco_admin_token";

export function AdminLogin({
  onSuccess,
  onCancel,
}: {
  onSuccess: (token: string) => void;
  onCancel: () => void;
}) {
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function entrar(e: FormEvent) {
    e.preventDefault();
    if (!clave || enviando) return;
    setEnviando(true);
    setError("");
    try {
      const resp = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: clave }),
      });
      if (!resp.ok) {
        const datos = await resp.json().catch(() => null);
        throw new Error(datos?.detail ?? "No se pudo iniciar sesión.");
      }
      const { token } = await resp.json();
      onSuccess(token);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "Error inesperado.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="utility-backdrop" onMouseDown={onCancel}>
      <section className="utility-panel admin-login" onMouseDown={(e) => e.stopPropagation()}>
        <button className="utility-close" onClick={onCancel}>×</button>
        <Icon name="shield" size={30} />
        <small>ACCESO RESTRINGIDO</small>
        <h3>Panel administrativo</h3>
        <form onSubmit={entrar}>
          <input
            type="password"
            autoFocus
            placeholder="Contraseña de administrador"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
          />
          {error && <div className="alert-banner error"><span>{error}</span></div>}
          <button className="utility-action" type="submit" disabled={!clave || enviando}>
            {enviando ? "VERIFICANDO…" : "ENTRAR"}
          </button>
        </form>
      </section>
    </div>
  );
}