/**
 * Catálogo de ecuaciones del agente (fuente única de la Fase B).
 *
 * Cada ecuación tiene una numeración ESTABLE (Ec.1 – Ec.20) que coincide con la
 * usada en el informe Markdown del backend, en la traza de inferencia y en la
 * memoria académica. NO cambiar el orden ni el número: los componentes de la
 * interfaz citan estas ecuaciones por su número.
 *
 * Las fórmulas se muestran como texto legible (notación matemática en ASCII /
 * LaTeX simplificado) para que puedan copiarse directamente en la defensa.
 */

/** Una variable o símbolo de una ecuación, con su significado. */
export interface VariableEcuacion {
  simbolo: string;
  significado: string;
}

/** Ecuación del modelo con su numeración fija. */
export interface Ecuacion {
  numero: number;
  id: string;
  nombre: string;
  formula: string;
  descripcion: string;
  variables?: VariableEcuacion[];
}

/**
 * Las 20 ecuaciones del proyecto, en el orden oficial.
 *
 * Bloque 1 (Ec.1–3): representación TF-IDF del texto.
 * Bloque 2 (Ec.4–5): clasificador lineal y su objetivo de entrenamiento.
 * Bloque 3 (Ec.6–7): calibración de probabilidades.
 * Bloque 4 (Ec.8–9): margen y umbrales de decisión.
 * Bloque 5 (Ec.10–16): métricas de evaluación y calibración.
 * Bloque 6 (Ec.17–18): intervalos de confianza y acuerdo entre anotadores.
 * Bloque 7 (Ec.19–20): modelos generativos y regresión logística.
 */
export const ECUACIONES: Ecuacion[] = [
  {
    numero: 1,
    id: "tf",
    nombre: "Frecuencia del término (TF)",
    formula: "tf(t, d) = nº de veces que el término t aparece en el documento d",
    descripcion:
      "Cuenta cuántas veces aparece un término (una palabra o un bigrama) en la solicitud.",
    variables: [
      { simbolo: "t", significado: "término (unigrama o bigrama)" },
      { simbolo: "d", significado: "documento (solicitud ciudadana)" },
    ],
  },
  {
    numero: 2,
    id: "idf",
    nombre: "Frecuencia inversa de documento (IDF)",
    formula: "idf(t) = ln((1 + N) / (1 + df(t))) + 1",
    descripcion:
      "Penaliza los términos que aparecen en muchas solicitudes y premia los que son selectivos de una categoría.",
    variables: [
      { simbolo: "N", significado: "nº total de documentos de entrenamiento" },
      { simbolo: "df(t)", significado: "nº de documentos que contienen el término t" },
    ],
  },
  {
    numero: 3,
    id: "tfidf",
    nombre: "Peso TF-IDF y normalización L2",
    formula: "tfidf(t, d) = tf(t, d) · idf(t)   ‖x‖₂ = ( Σᵢ xᵢ² )^(1/2)   x̂ = x / ‖x‖₂",
    descripcion:
      "Combina la frecuencia local con la rareza global y normaliza el vector del documento a norma 1 para que su longitud no altere la comparación.",
    variables: [
      { simbolo: "x", significado: "vector de pesos TF-IDF del documento" },
      { simbolo: "x̂", significado: "vector normalizado (norma L2 unitaria)" },
    ],
  },
  {
    numero: 4,
    id: "decision",
    nombre: "Puntaje de decisión lineal",
    formula: "s_c(x) = w_c · x + b_c",
    descripcion:
      "Valor que asigna cada clase c al vector x: producto punto de sus coeficientes aprendidos más el sesgo. Gana la clase con mayor puntaje.",
    variables: [
      { simbolo: "w_c", significado: "vector de coeficientes de la clase c" },
      { simbolo: "b_c", significado: "sesgo (intercepto) de la clase c" },
    ],
  },
  {
    numero: 5,
    id: "svm",
    nombre: "Objetivo del clasificador de margen (SVM)",
    formula: "mín ½‖w‖² + C Σᵢ ξᵢ   sujeto a  yᵢ(w·xᵢ + b) ≥ 1 − ξᵢ,  ξᵢ ≥ 0",
    descripcion:
      "El SVM busca el hiperplano que separa las clases con el mayor margen posible, penalizando los errores con el parámetro C.",
    variables: [
      { simbolo: "C", significado: "parámetro de penalización de errores" },
      { simbolo: "ξᵢ", significado: "holgura (error permitido) del ejemplo i" },
    ],
  },
  {
    numero: 6,
    id: "platt",
    nombre: "Calibración de Platt",
    formula: "P(y = 1 | s) = 1 / (1 + exp(A·s + B))",
    descripcion:
      "Convierte el puntaje bruto s del clasificador en una probabilidad calibrada mediante una sigmoide ajustada con datos.",
    variables: [
      { simbolo: "s", significado: "puntaje de decisión del clasificador" },
      { simbolo: "A, B", significado: "parámetros de la sigmoide estimados por máxima verosimilitud" },
    ],
  },
  {
    numero: 7,
    id: "normalizacion-prob",
    nombre: "Normalización de probabilidades",
    formula: "P(c | x) = P̂(c | x) / Σ_{c'} P̂(c' | x),   Σ_c P(c | x) = 1",
    descripcion:
      "Reescala las probabilidades calibradas para que sumen 1 y sean interpretables como porcentajes de confianza.",
  },
  {
    numero: 8,
    id: "margen",
    nombre: "Margen de decisión",
    formula: "margen = P(c₁ | x) − P(c₂ | x)",
    descripcion:
      "Diferencia entre la probabilidad de la clase más probable y la segunda. Un margen pequeño indica indecisión del modelo.",
    variables: [
      { simbolo: "c₁", significado: "clase más probable (top-1)" },
      { simbolo: "c₂", significado: "segunda clase más probable (top-2)" },
    ],
  },
  {
    numero: 9,
    id: "umbrales",
    nombre: "Umbrales de decisión (revisión humana)",
    formula: "aceptar  ⇔  confianza ≥ 60 %  ∧  margen ≥ 15 %;  en caso contrario → revisión humana",
    descripcion:
      "Regla operativa: si la confianza o el margen quedan por debajo de los umbrales, la solicitud se marca para revisión humana.",
    variables: [
      { simbolo: "umbral_confianza", significado: "60 % (configurable en el backend)" },
      { simbolo: "umbral_margen", significado: "15 % (configurable en el backend)" },
    ],
  },
  {
    numero: 10,
    id: "accuracy",
    nombre: "Exactitud (accuracy)",
    formula: "accuracy = (VP + VN) / (VP + VN + FP + FN)",
    descripcion:
      "Proporción de predicciones correctas sobre el total de casos evaluados.",
    variables: [
      { simbolo: "VP", significado: "verdaderos positivos" },
      { simbolo: "VN", significado: "verdaderos negativos" },
      { simbolo: "FP", significado: "falsos positivos" },
      { simbolo: "FN", significado: "falsos negativos" },
    ],
  },
  {
    numero: 11,
    id: "precision",
    nombre: "Precisión",
    formula: "precisión = VP / (VP + FP)",
    descripcion:
      "De todas las solicitudes que el modelo asignó a una clase, qué fracción era correcta.",
  },
  {
    numero: 12,
    id: "recall",
    nombre: "Exhaustividad (recall)",
    formula: "recall = VP / (VP + FN)",
    descripcion:
      "De todas las solicitudes que realmente pertenecían a una clase, qué fracción detectó el modelo.",
  },
  {
    numero: 13,
    id: "f1",
    nombre: "F1 (media armónica)",
    formula: "F1 = 2 · (precisión · recall) / (precisión + recall)",
    descripcion:
      "Equilibra precisión y recall en un único número; penaliza los modelos que sacrifican uno por el otro.",
  },
  {
    numero: 14,
    id: "f1-macro",
    nombre: "F1 macro",
    formula: "F1_macro = (1 / K) Σ_{k=1}^{K} F1_k",
    descripcion:
      "Promedio del F1 de cada clase sin ponderar por su tamaño: la métrica principal del proyecto.",
    variables: [{ simbolo: "K", significado: "nº de clases (8 categorías o 3 prioridades)" }],
  },
  {
    numero: 15,
    id: "brier",
    nombre: "Brier score",
    formula: "BS = (1 / N) Σᵢ ( p̂ᵢ − yᵢ )²",
    descripcion:
      "Error cuadrático medio entre la probabilidad predicha y el resultado real. Más bajo = mejor calibrado.",
    variables: [
      { simbolo: "p̂ᵢ", significado: "probabilidad predicha para el caso i" },
      { simbolo: "yᵢ", significado: "resultado real (1 si acierta, 0 si no)" },
    ],
  },
  {
    numero: 16,
    id: "ece",
    nombre: "Error de calibración esperado (ECE)",
    formula: "ECE = Σ_{m=1}^{M} (n_m / N) · | acierto_m − confianza_m |",
    descripcion:
      "Diferencia media entre la confianza declarada y la exactitud real, agrupada por rangos de confianza.",
    variables: [
      { simbolo: "M", significado: "nº de intervalos (bins) de confianza" },
      { simbolo: "n_m", significado: "nº de casos en el intervalo m" },
    ],
  },
  {
    numero: 17,
    id: "wilson",
    nombre: "Intervalo de confianza de Wilson",
    formula:
      "( p + z²/2n ± z·√( p(1−p)/n + z²/4n² ) ) / ( 1 + z²/n )",
    descripcion:
      "Intervalo de confianza de una proporción fiable con pocos casos; se usa para reportar la exactitud con su margen de error al 95 %.",
    variables: [
      { simbolo: "p", significado: "proporción observada (aciertos / n)" },
      { simbolo: "n", significado: "nº de observaciones" },
      { simbolo: "z", significado: "valor de la normal (1.96 para el 95 %)" },
    ],
  },
  {
    numero: 18,
    id: "kappa",
    nombre: "Kappa de Cohen",
    formula: "κ = (p₀ − pₑ) / (1 − pₑ)",
    descripcion:
      "Mide el acuerdo entre dos etiquetadores corrigiendo el acuerdo esperado por azar.",
    variables: [
      { simbolo: "p₀", significado: "acuerdo observado" },
      { simbolo: "pₑ", significado: "acuerdo esperado por azar" },
    ],
  },
  {
    numero: 19,
    id: "naive-bayes",
    nombre: "Naive Bayes multinomial",
    formula: "P(c | x) ∝ P(c) · Π_t P(t | c)^{x_t}",
    descripcion:
      "Modelo generativo que supone independencia entre términos; sirve como alternativa y baseline frente al clasificador lineal.",
    variables: [
      { simbolo: "P(c)", significado: "probabilidad a priori de la clase c" },
      { simbolo: "x_t", significado: "peso del término t en el documento" },
    ],
  },
  {
    numero: 20,
    id: "softmax",
    nombre: "Función Softmax (regresión logística multiclase)",
    formula: "P(c | x) = exp(s_c(x)) / Σ_{c'} exp(s_{c'}(x))",
    descripcion:
      "Convierte los puntajes de decisión de todas las clases en una distribución de probabilidad que suma 1.",
    variables: [
      { simbolo: "s_c(x)", significado: "puntaje de decisión de la clase c (Ec.4)" },
    ],
  },
];

/** Busca una ecuación por su número (1–20). */
export function ecuacionPorNumero(numero: number): Ecuacion | undefined {
  return ECUACIONES.find((ecuacion) => ecuacion.numero === numero);
}

/** Busca una ecuación por su identificador textual (p. ej. "tfidf"). */
export function ecuacionPorId(id: string): Ecuacion | undefined {
  return ECUACIONES.find((ecuacion) => ecuacion.id === id);
}

/** Devuelve la etiqueta corta "Ec.N" usada en la interfaz. */
export function etiquetaEcuacion(numero: number): string {
  return `Ec.${numero}`;
}
