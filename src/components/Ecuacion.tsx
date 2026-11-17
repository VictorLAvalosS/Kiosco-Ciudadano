import type { Ecuacion } from "@/lib/ecuaciones";
import { ecuacionPorNumero } from "@/lib/ecuaciones";

/**
 * Ficha de una ecuación del catálogo (Ec.1–20).
 *
 * Se usa en la traza del agente y en la página del modelo para mostrar, junto a
 * cada paso real del pipeline, la fórmula que lo sustenta. La numeración
 * proviene de `src/lib/ecuaciones.ts` (fuente única).
 */
export function EcuacionCard({ numero, compacto = false }: { numero: number; compacto?: boolean }) {
  const ecuacion = ecuacionPorNumero(numero);
  if (!ecuacion) return null;
  return (
    <article className={`ecuacion-card ${compacto ? "compacta" : ""}`}>
      <header>
        <span>{`Ec.${ecuacion.numero}`}</span>
        <b>{ecuacion.nombre}</b>
      </header>
      <code>{ecuacion.formula}</code>
      {!compacto && <p>{ecuacion.descripcion}</p>}
      {!compacto && ecuacion.variables && ecuacion.variables.length > 0 && (
        <ul className="ecuacion-vars">
          {ecuacion.variables.map((variable) => (
            <li key={variable.simbolo}>
              <i>{variable.simbolo}</i>
              <span>{variable.significado}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

/** Fila de varias ecuaciones del catálogo. */
export function EcuacionLista({
  numeros,
  compacto = false,
}: {
  numeros: number[];
  compacto?: boolean;
}) {
  if (numeros.length === 0) return null;
  return (
    <div className="ecuacion-lista">
      {numeros.map((numero) => (
        <EcuacionCard key={numero} numero={numero} compacto={compacto} />
      ))}
    </div>
  );
}

/** Reexporta el tipo para los componentes que reciben ecuaciones. */
export type { Ecuacion };
