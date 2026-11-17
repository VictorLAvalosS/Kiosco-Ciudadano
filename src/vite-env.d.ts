/// <reference types="vite/client" />

/** Variables de entorno del frontend expuestas por Vite (prefijo VITE_). */
interface ImportMetaEnv {
  /** Clave de API opcional: debe coincidir con `API_KEY` del backend. */
  readonly VITE_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
