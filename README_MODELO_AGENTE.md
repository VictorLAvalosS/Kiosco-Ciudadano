# Guía del panel «Modelo agente»

Esta guía explica en lenguaje sencillo la información de la pantalla **Modelo agente** del panel administrativo. Los datos que aparecen allí proceden del modelo entrenado, las solicitudes etiquetadas y las evaluaciones guardadas por el backend; no son cifras de ejemplo.

## ¿Qué hace el agente?

El agente recibe el texto libre de una solicitud ciudadana y predice dos cosas:

1. **Categoría**: el área a la que corresponde, por ejemplo agua, alumbrado, limpieza o calles.
2. **Prioridad**: alta, media o baja.

Es un sistema de aprendizaje supervisado: aprende de solicitudes que el equipo ya etiquetó. El texto se normaliza, se convierte en características numéricas TF-IDF y se procesa con el algoritmo mostrado en la pantalla. La predicción ayuda a derivar la solicitud; los casos con poca confianza o poca diferencia entre opciones se marcan para revisión humana.

## Encabezado y ciclo de trabajo

- **Versión activa** identifica el modelo que se usa actualmente.
- **Algoritmo** indica el clasificador seleccionado durante el entrenamiento.
- **Evaluación** informa si las métricas se calcularon con un conjunto de prueba fijo o, cuando aún no se puede reservar una prueba, mediante validación cruzada.
- **Entrenado** es la fecha y hora guardada para esa versión.
- **Reentrenar agente** crea una versión usando las etiquetas disponibles. El sistema la activa si es comparable y su F1 macro supera al de la versión activa. Si no mejora, la versión anterior permanece activa.
- **Forzar activación** permite activar una versión que normalmente no se considera comparable. Úsese con cuidado: puede invalidar una comparación justa con otras versiones.

El ciclo mostrado debajo resume el proceso: etiquetar solicitudes, reentrenar, evaluar, decidir qué versión activar, operar con revisión humana para dudas y volver a aprender de nuevas etiquetas.

## Datos y particiones

El bloque **Conjunto de datos** muestra el número de ejemplos que forman las particiones registradas para esa versión:

- **Entrenamiento**: ejemplos usados para ajustar el modelo.
- **Validación**: ejemplos usados durante la selección o validación del modelo, según el método registrado.
- **Prueba fija**: ejemplos reservados para medir el resultado final; no deben usarse para entrenar esa versión.

La suma mostrada es la suma de esas tres cantidades, no necesariamente el total de todas las etiquetas actuales de la base de datos. El conjunto de prueba fijo se conserva para comparar versiones sobre los mismos casos. El sistema también procura separar textos casi duplicados para reducir la fuga de información entre entrenamiento y prueba.

Si aparecen menos de 30 ejemplos por clase, el panel avisa que los datos son insuficientes y que las métricas son preliminares. Pocas etiquetas hacen que una o dos solicitudes cambien mucho los porcentajes.

## ¿Qué significa Accuracy?

**Accuracy (exactitud)** es la proporción de predicciones correctas entre todos los casos evaluados:

`accuracy = casos clasificados correctamente / total de casos evaluados`

Por ejemplo, 80% significa que el modelo acertó 80 de cada 100 casos de esa evaluación. El porcentaje por sí solo no cuenta toda la historia: si una categoría aparece mucho más que las demás, un modelo puede obtener una accuracy alta favoreciendo la categoría común y fallar en las categorías menos frecuentes. Por eso el panel también muestra precisión macro, recall macro y F1 macro.

Las métricas principales se calculan tanto para **categoría** como para **prioridad**. Son tareas separadas: una solicitud puede tener la categoría correcta y la prioridad equivocada, o viceversa.

## Métricas de clasificación

Para entender las fórmulas, se puede mirar una clase concreta como si fuera “positiva” y todas las demás como “no esa clase”:

- **VP (verdadero positivo)**: el caso sí era de esa clase y el modelo la predijo.
- **FP (falso positivo)**: el modelo predijo esa clase, pero el caso era de otra.
- **FN (falso negativo)**: el caso sí era de esa clase, pero el modelo predijo otra.
- **VN (verdadero negativo)**: el caso era de otra clase y el modelo no lo asignó a esta.

| Métrica | Qué responde | Fórmula / lectura |
|---|---|---|
| **Accuracy** | ¿Qué fracción de todos los casos acertó? | Aciertos totales / casos totales. |
| **Precisión (precision)** | Cuando el modelo asigna una clase, ¿con qué frecuencia acierta? | `VP / (VP + FP)`. Una precisión baja implica más falsas asignaciones a esa clase. |
| **Recall (exhaustividad)** | De los casos que realmente eran de una clase, ¿cuántos encontró? | `VP / (VP + FN)`. Un recall bajo implica que se le escapan casos de esa clase. |
| **F1** | ¿Cómo equilibra precisión y recall para una clase? | Media armónica: `2 × precisión × recall / (precisión + recall)`. |
| **Macro** | ¿Cómo se promedian las clases? | Se calcula la métrica de cada clase y luego se promedian todas por igual, sin dar más peso a las clases grandes. |
| **F1 macro** | ¿Qué tan equilibrado es el desempeño entre clases? | Promedio del F1 de cada clase. Es la métrica principal para comparar y activar versiones. |

Accuracy considera el conjunto completo y puede verse dominada por las clases frecuentes. Las métricas macro dan el mismo peso a cada clase, por eso ayudan a detectar si el agente descuida alguna categoría pequeña. F1 macro alto y parecido a accuracy suele indicar un desempeño más equilibrado; conviene revisar también las métricas por clase y las confusiones.

## Métricas por categoría o prioridad

Las tablas muestran una fila por etiqueta:

- **P**: precisión de esa clase.
- **R**: recall de esa clase.
- **F1**: equilibrio entre P y R para esa clase.
- **N (soporte)**: cantidad de casos reales de esa clase en la evaluación.

Un porcentaje en una clase con un N muy pequeño es menos estable que el mismo porcentaje calculado con muchos casos. Estas métricas por clase permiten localizar dónde funciona bien o mal el modelo.

## Matriz de confusión

Hay una matriz para categoría y otra para prioridad. Las **filas son la etiqueta real** y las **columnas la predicción**. Cada celda indica cuántos casos reales de una fila se asignaron a la columna.

- Los valores de la diagonal son aciertos.
- Los valores fuera de la diagonal son errores: muestran qué clases se confundieron.
- **Absoluta** presenta cantidades de casos.
- **Normalizada** divide cada fila por su total real; cada valor es la proporción de esa clase real que terminó en cada predicción. La diagonal normalizada corresponde al recall de cada clase.

La lista de **pares más confundidos** resume los errores fuera de la diagonal más frecuentes, indicando etiqueta real → etiqueta predicha.

## Curvas y comparación de modelos

- **Curva de aprendizaje**: eje X = cantidad de ejemplos; eje Y = F1 macro. Compara F1 de entrenamiento y validación. Si entrenamiento queda alto y validación mucho más baja, el modelo puede estar memorizando los ejemplos o necesitar más datos representativos. Si ambas curvas son bajas, puede faltar información o mejorar las etiquetas y características.
- **Comparación de algoritmos**: muestra el F1 macro de los algoritmos candidatos evaluados con validación cruzada estratificada. El ganador indicado es el seleccionado para esa versión. La validación cruzada divide repetidamente los datos para estimar el desempeño sin depender de una sola partición.
- **Baselines**: comparan el agente con reglas sencillas. “Clase mayoritaria” siempre predice la clase más frecuente; “aleatorio estratificado” predice al azar respetando las proporciones observadas. Si el agente no los supera, no hay evidencia clara de que aporte valor frente a esas reglas. Se muestran cuando hay conjunto de prueba disponible.
- **Mejora por volumen de etiquetas**: F1 macro medio al entrenar con distintas fracciones de datos, usando cinco semillas y el mismo conjunto de prueba. `±` es la desviación estándar entre repeticiones; menor variación indica resultados más consistentes. No es una garantía de que cada nueva etiqueta mejore el resultado.
- **Evolución por versión**: presenta F1 macro y accuracy de versiones comparables. Las versiones marcadas como no comparables se omiten porque su evaluación o datos no permiten una comparación justa.

## Confianza, calibración y revisión humana

La **confianza** de una predicción es la probabilidad estimada para la clase que el modelo eligió. No equivale automáticamente a una garantía de acierto: una confianza de 80% solo se interpreta como “aproximadamente 8 de cada 10 aciertos” si las probabilidades están bien calibradas y se verifica en suficientes casos similares.

- **Calibración** agrupa predicciones por rangos de confianza y compara confianza media con porcentaje de aciertos real. Si un grupo con confianza media cercana a 70% acierta cerca de 70%, sus probabilidades están razonablemente calibradas en ese rango.
- **Brier score** y **ECE** resumen errores de calibración; valores menores suelen ser mejores. El Brier compara probabilidades con resultados reales; ECE mide la diferencia entre confianza y acierto por intervalos.
- **Curva cobertura-precisión** muestra el compromiso al cambiar el umbral: cobertura es la proporción de casos que el sistema aceptaría automáticamente; precisión es la proporción de aciertos entre esos aceptados. Al elevar el umbral suele bajar la cobertura y subir la precisión, aunque los datos pueden variar.
- **Umbral de confianza**: mínimo de confianza exigido.
- **Umbral de margen**: mínima diferencia entre la probabilidad de la clase elegida y la segunda opción. Una diferencia pequeña significa que el modelo duda entre ambas.

En la configuración habitual, se acepta automáticamente solo si se alcanzan ambos umbrales (por ejemplo, confianza de 60% y margen de 15%, si esos son los valores que muestra la versión). Si no, se marca **requiere revisión humana**. Los umbrales exactos pueden configurarse en el backend; hay que leer los valores visibles para conocer los vigentes.

## Prueba externa y análisis de errores

El bloque **Conjunto de prueba externo** evalúa solicitudes nuevas identificadas con origen `prueba_externa`, nunca utilizadas para entrenar. Sus cifras pueden ser diferentes y menores que las de la prueba fija porque representan textos nuevos. Si no hay registros externos, el bloque no aparece.

**Análisis de errores** lista hasta diez solicitudes de la evaluación cuya categoría fue predicha incorrectamente, con etiqueta real, predicción y confianza. Es una herramienta para encontrar patrones de error y revisar etiquetas; una confianza alta no elimina la posibilidad de equivocación.

## Calidad del dataset y acuerdo entre etiquetadores

- **Etiquetas vigentes**: cantidad de etiquetas actualmente consideradas válidas para el informe de calidad.
- **Duplicados exactos**: grupos de textos iguales después de normalizar mayúsculas, tildes y formato.
- **Casi-duplicados**: textos similares según TF-IDF y similitud coseno; se usa para advertir posibles ejemplos repetidos o fuga de datos.
- **Etiquetas contradictorias**: textos iguales que tienen categorías distintas.
- **Vocabulario único**: número de términos distintos reconocidos en los textos.
- **Razón máximo/mínimo por clase**: cantidad de ejemplos de la clase más numerosa dividida por la menos numerosa. Cuanto más alta, mayor desbalance.
- **Kappa de Cohen**: acuerdo entre dos personas que etiquetaron casos compartidos, descontando el acuerdo que podría ocurrir por azar. Se muestra por separado para categoría y prioridad. Si no hay solicitudes con más de una etiqueta, no puede calcularse.

Estas cifras ayudan a juzgar la calidad de la evaluación: un modelo puede parecer débil por falta de datos, clases desbalanceadas o etiquetas inconsistentes, y las métricas no explican por sí solas la causa.

## Términos influyentes

Los **términos más influyentes por categoría** son palabras o grupos de palabras (n-gramas) con pesos altos para cada clase según el clasificador. Sirven para inspeccionar qué vocabulario caracteriza a una categoría; no son una explicación causal ni una regla fija que el sistema aplique literalmente.

## Historial y parámetros

- **Historial de versiones** conserva las versiones entrenadas y permite activar una versión anterior (rollback) cuando corresponde.
- **Hiperparámetros** son ajustes internos del clasificador. `C` controla regularización en modelos lineales; `alpha` es la intensidad de suavizado en modelos que lo usan; `class_weight` ajusta el peso de clases; `max_iter` limita iteraciones. Los que no se aplican al algoritmo seleccionado pueden aparecer vacíos.
- **Calibrado (Platt)** indica si se ajustó una transformación de las puntuaciones para estimar probabilidades más interpretables.
- **TF-IDF** convierte texto en números según la importancia de cada término en el documento y el corpus. `n-gramas 1–2` considera palabras individuales y pares de palabras; `min_df` descarta términos que aparecen en muy pocos documentos; `sublinear_tf` suaviza el peso por frecuencia. “Características” es el número de atributos textuales del vector; “vocabulario” es el tamaño del conjunto de términos.
- **Semilla** fija parte del azar para poder repetir una partición. **Folds máx.** es el máximo de particiones de validación cruzada permitido por la cantidad disponible en las clases.
- **Eficiencia medida** presenta el tiempo observado de entrenamiento, tamaño guardado del modelo, latencia media y p95. p95 significa que 95% de las predicciones medidas tardó ese tiempo o menos. Son mediciones del entorno donde se entrenó y no una garantía de latencia en cualquier equipo.
- **Informe del agente** permite consultar o exportar detalles adicionales del modelo y la evaluación desde la interfaz.

## Cómo leer los resultados con criterio

1. Comprueba el método y el tamaño de la prueba antes de interpretar un porcentaje.
2. Revisa F1 macro y las métricas por clase junto con accuracy; no evalúes el modelo por una sola cifra.
3. Inspecciona la matriz, los pares confundidos y los errores para identificar problemas concretos.
4. Contrasta las métricas con baselines y, cuando exista, con la prueba externa.
5. Revisa calibración y umbrales: las predicciones dudosas deben pasar por revisión humana.
6. Valora el número y la calidad de las etiquetas. Resultados altos en una prueba pequeña no garantizan el mismo desempeño con solicitudes futuras.

Las métricas describen el comportamiento observado en los datos de evaluación disponibles; no prometen que todas las solicitudes futuras se clasifiquen correctamente.
