export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <div className="brand-mark">
        <span />
        <span />
        <span />
      </div>
      {!compact && (
        <div>
          <b>OTB CONECTADA</b>
          <small>GESTIÓN TERRITORIAL CIUDADANA</small>
        </div>
      )}
    </div>
  );
}

export function StatusPill() {
  return (
    <div className="status-pill">
      <span className="status-dot" />
      <span>
        <b>SISTEMA EN LÍNEA</b>
        <small>Agente IA escuchando peticiones</small>
      </span>
    </div>
  );
}

export function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="admin-toast">
      <span>✓</span>
      {message}
    </div>
  );
}
