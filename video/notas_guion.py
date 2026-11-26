"""Guion literal de cada diapositiva: lo que dice cada persona, tal cual.

Dimensionado a ~140 palabras por minuto: ~4 min por bloque (Personas 1, 2 y 4) y,
para la Persona 3, ~3 min hablados + las esperas reales de la demo (≈8 min).
"""

NOTES = {
1: ("PERSONA 1 · METODOLOGÍA (0:00–0:35)",
"""Hola a todos. Somos un grupo de cuatro integrantes y les presentamos el Laboratorio 4: un asistente de compras por voz en español.

El asistente escucha al usuario, busca productos en un catálogo real de Amazon, opera sobre una tienda simulada y responde hablando, con la voz clonada de uno de nosotros. Todo corre dentro de Google Colab, en una GPU T4, sin APIs externas.

Nos dividimos el video en cuatro partes: metodología, implementación, una demostración en vivo y resultados. Empiezo yo con la metodología."""),

2: ("PERSONA 1 · METODOLOGÍA (0:35–1:25)",
"""El asistente debe cumplir cinco capacidades.

Uno: entender la voz en español, y permitir corregir la transcripción antes de comprar.

Dos: buscar con evidencia. Solo recomienda lo que el catálogo respalda; si un dato no aparece en el producto, lo trata como desconocido.

Tres: actuar sobre la tienda. Consulta precios y stock, arma el carrito, cotiza y registra el pedido, pero solo con una confirmación explícita.

Cuatro: recordar el presupuesto, las cantidades y las preferencias, y preguntar cuando falta información.

Y cinco: responder por voz, con la voz clonada.

El reto es que todo funcione junto, con garantías, dentro de los quince gigas de una T4."""),

3: ("PERSONA 1 · METODOLOGÍA (1:25–2:20)",
"""Esta es la arquitectura de un turno.

El usuario habla y Whisper transcribe el audio. El texto entra al agente, que es Qwen3 de ocho mil millones de parámetros, cargado en cuatro bits.

El agente no responde de memoria: decide qué herramienta usar. Abajo a la izquierda están las herramientas: la búsqueda en el catálogo y las operaciones de la tienda. A la derecha, la memoria estructurada: presupuesto, preferencias, productos mostrados y cotización. Esa memoria se le pasa al modelo en cada paso.

Al final, XTTS convierte la respuesta en audio con la voz clonada.

Una decisión clave: las garantías, como la confirmación, el presupuesto y el stock, están en el código, no en el modelo de lenguaje."""),

4: ("PERSONA 1 · METODOLOGÍA (2:20–3:10)",
"""Los datos vienen del dataset ESCI de Amazon, en su versión reducida en español.

Armamos un catálogo de quince mil productos: los anotados de las consultas elegidas, más distractores para que la búsqueda no sea trivial.

Usamos ciento cincuenta consultas de desarrollo y doscientas cincuenta de evaluación, separadas por consulta. Todo se ajusta con las de desarrollo; las de evaluación no se tocan.

Las etiquetas de relevancia solo sirven para medir la búsqueda; el agente nunca las ve.

Y la tienda simulada genera precios, stock y pedidos con una semilla fija y se puede restaurar, así cada prueba empieza desde el mismo estado."""),

5: ("PERSONA 1 · METODOLOGÍA (3:10–4:00)",
"""Estos son los seis modelos, todos preentrenados y abiertos.

Para buscar usamos e5, un modelo de embeddings multilingüe, y el re-ranker bge, que es lo que más mejora la búsqueda.

El modelo de lenguaje es Qwen3 de ocho mil millones. Lo elegimos porque llama herramientas de forma nativa, y en cuatro bits ocupa unos seis gigas.

Para la voz, Whisper turbo transcribe rápido y con buena calidad, y XTTS clona la voz con pocos segundos de grabación. WavLM solo mide qué tan parecida es la voz clonada.

Con todo cargado usamos once punto siete gigas de los quince punto seis de la T4.

Ahora pasamos a la implementación."""),

6: ("PERSONA 2 · IMPLEMENTACIÓN (4:00–5:00)",
"""Gracias. Empiezo por la búsqueda.

Combinamos dos buscadores. BM25, que implementamos nosotros, es bueno con coincidencias literales: marcas, modelos o cifras. El buscador denso con e5 entiende el significado y los sinónimos.

Juntamos sus resultados con fusión por rango recíproco, con pesos ajustados solo en desarrollo. Luego, el re-ranker lee la consulta junto con cada candidato y los reordena con más precisión.

Al agente le devolvemos evidencia: título, precio y atributos que aparecen en el texto. Si el usuario pregunta algo que el catálogo no dice, la respuesta es «desconocido». Y filtros como el precio máximo se aplican en el código."""),

7: ("PERSONA 2 · IMPLEMENTACIÓN (5:00–6:00)",
"""Ahora el agente, que funciona como un bucle.

En cada paso, el modelo recibe el mensaje y la memoria, y propone una herramienta. El código la valida, la ejecuta y le devuelve el resultado, hasta seis veces por turno. Al final, el modelo redacta la respuesta.

A la derecha están las reglas que añadimos. El pedido solo se confirma con un «sí, confirmo» explícito. El presupuesto y el color se guardan en la memoria por regla. Los importes los calcula el código, así nunca hay cifras inventadas.

Y dos correcciones: si el usuario ya eligió y el modelo solo pregunta, le pedimos que actúe; y si dice que añadió algo al carrito pero no lo hizo, le pedimos que lo haga."""),

8: ("PERSONA 2 · IMPLEMENTACIÓN (6:00–7:00)",
"""La tienda simulada concentra las garantías que pide el enunciado.

Cantidades, presupuesto y stock se validan en cada operación. Al confirmar, se revisan de nuevo el precio y el stock, porque pueden cambiar.

El pedido es atómico: pedido e inventario cambian juntos o no cambia nada. Es idempotente: confirmar dos veces no duplica el pedido. Y sin cotización vigente o sin un «sí» explícito, la confirmación se rechaza.

Además, la tienda se restaura con la misma semilla, así las pruebas son reproducibles.

Gracias a esto, en todas las pruebas, incluso apagando las reglas del agente, hubo cero incumplimientos de restricciones."""),

9: ("PERSONA 2 · IMPLEMENTACIÓN (7:00–8:00)",
"""También gestionamos la memoria de la GPU. El gráfico muestra la memoria que se va ocupando al cargar cada modelo.

El que más ocupa es el modelo de lenguaje, unos seis gigas, porque lo cargamos en cuatro bits; sin eso necesitaría dieciséis y no cabría.

Además, procesamos los textos largos por bloques y cada modelo se carga una sola vez. Con los seis cargados llegamos a once punto siete gigas de quince punto seis.

Ahora veamos el asistente funcionando."""),

10: ("PERSONA 3 · DEMOSTRACIÓN (8:00–8:40)",
"""Gracias. Ahora vamos a ver el asistente en vivo, en Colab.

Voy a mostrar dos casos. El primero es una compra completa por voz: busco un producto con un presupuesto, elijo, pido la cotización y confirmo el pedido. El segundo es una petición ambigua, donde el asistente tiene que preguntarme antes de actuar.

Fíjense en tres cosas: la transcripción de lo que digo, que puedo corregir antes de que se ejecute; las herramientas que va llamando el agente; y el tiempo que tarda cada etapa.

No vamos a cortar la espera, porque queremos que vean el tiempo real. En esta GPU, cada respuesta tarda alrededor de treinta segundos. Vamos a Colab."""),

11: ("PERSONA 3 · DEMOSTRACIÓN EN COLAB (8:40–14:30)",
"""Esta es la celda de la demostración. Cuando la ejecuto, aparece este botón rojo y el sistema ya me está escuchando.

[Al micrófono] «Quiero dos botellas de agua reutilizables, mi presupuesto es de cuarenta euros.»

Ahí aparece la transcripción. Está bien, así que la acepto. Mientras procesa: Whisper ya transcribió, ahora el agente está buscando en el catálogo con el precio máximo, y el re-ranker ordena los candidatos. Ahí responde, con la voz clonada, y abajo se ven los tiempos de cada etapa.

[Al micrófono] «Me quedo con la primera, prepárame la cotización.»

Ahora el agente añade dos unidades al carrito y pide la cotización. El resumen con los importes lo genera el código, por eso las cifras siempre son exactas.

[Al micrófono] «Sí, confirmo el pedido.»

Y el pedido queda registrado. Si no hubiera dicho «sí, confirmo» de forma explícita, la tienda lo habría rechazado.

Ahora el segundo caso.

[Al micrófono] «Necesito un cargador.»

Esta petición es ambigua: no dije para qué dispositivo. Por eso el asistente me pregunta antes de tocar el carrito.

[Al micrófono] «Es para un móvil con USB C, solo uno, el primero que muestres. Cotiza.»

Con esa información ya puede buscar, añadir el cargador y cotizar.

[Al micrófono] «Sí, confirmo.»

Segundo pedido registrado. Escribo «fin» y se muestra el estado final: lo que recordó el agente durante la conversación y los pedidos que se hicieron."""),

12: ("PERSONA 3 · DEMOSTRACIÓN (14:30–16:00)",
"""Además de esta demostración en vivo, el notebook evalúa de forma reproducible las seis situaciones por voz que pide el enunciado.

Son: una compra que termina en pedido; una solicitud ambigua que requiere aclaración; un cambio de cantidad que conserva el presupuesto; un producto agotado, donde el asistente propone una alternativa; la corrección de una transcripción, donde a propósito el sistema entiende «trece» en lugar de «tres» y se corrige antes de comprar; y un cambio de stock entre la cotización y la confirmación, donde confirmamos dos veces y el pedido no se duplica.

Para separar los errores del reconocimiento de voz de los del agente, repetimos cada caso con la transcripción correcta. El resultado fue seis de seis en las dos versiones, con un pedido final en cada escenario.

Ahora vemos los resultados completos."""),

13: ("PERSONA 4 · RESULTADOS (16:00–16:45)",
"""Gracias. Empiezo por la búsqueda, medida con nDCG arroba diez en las doscientas cincuenta consultas de evaluación.

El modelo base, BM25, logra cero punto seis nueve tres. Nuestro sistema completo llega a cero punto siete siete siete: una mejora de cero punto cero ocho cuatro, estadísticamente significativa. Sobre el catálogo completo sube de cero punto cinco nueve nueve a cero punto seis nueve siete.

En la ablación, quitar el re-ranker resta cero punto cero cuatro siete, y casi el doble en el catálogo completo. Es el componente que más aporta."""),

14: ("PERSONA 4 · RESULTADOS (16:45–17:30)",
"""En el agente evaluamos veintidós escenarios. El sistema completo resuelve diecinueve, un ochenta y seis por ciento.

En la ablación repetimos los mismos escenarios sin las reglas: baja a diez de veintidós, un cuarenta y cinco por ciento. Las reglas aportan unos cuarenta puntos.

Lo más importante: cero incumplimientos en las dos versiones. Aunque el modelo se equivoque, nunca hay pedidos sin confirmación, duplicados o fuera de presupuesto.

Eso sí, ajustamos las reglas mirando estos escenarios, así que el ochenta y seis por ciento es optimista."""),

15: ("PERSONA 4 · RESULTADOS (17:30–18:15)",
"""En voz, el reconocimiento tuvo un error por palabra de cero punto cero tres ocho, y cero errores en cantidades, importes y productos. Los turnos de usuario de esta evaluación fueron sintéticos, que es el mejor caso.

La voz clonada tiene una semejanza de cero punto nueve cinco dos con la original. Como referencia, la misma persona da cero punto nueve ocho seis y otra voz, cero punto seis seis tres. Está muy cerca de la original.

Su inteligibilidad tiene un error de cero punto dos cinco, sobre todo en cifras, siglas y marcas."""),

16: ("PERSONA 4 · RESULTADOS (18:15–18:45)",
"""Cada turno tarda en promedio veintiocho coma seis segundos en la T4. La transcripción y la búsqueda tardan menos de un segundo; el modelo de lenguaje, unos diecisiete, y la voz, unos diez. La carga inicial se mide aparte.

No es tiempo real, y el enunciado no lo exige. Con un modelo más pequeño o una GPU más rápida bajaría bastante."""),

17: ("PERSONA 4 · RESULTADOS (18:45–19:30)",
"""Ahora, aciertos y fallos.

Aciertos: las búsquedas con marca o modelo literal logran un resultado perfecto; la corrección de transcripción funciona; el cambio de stock no duplica pedidos; y la aclaración y el producto agotado ya se resuelven bien.

Fallos: en la búsqueda, las negaciones, como «carpetas sin anillas», y la compatibilidad de repuestos. En el agente, interpretó «tres mochilas» como tres productos distintos; una de nuestras reglas tomó «la primera» dentro de una pregunta como una elección; y una vez el modelo dijo que actualizó el carrito sin hacerlo. En los tres casos, la tienda evitó un pedido inválido."""),

18: ("PERSONA 4 · RESULTADOS (19:30–20:00)",
"""Para cerrar: el catálogo no tiene atributos estructurados, las reglas se basan en palabras y a veces fallan, cada turno tarda unos treinta segundos y la evaluación por voz usó turnos sintéticos.

En conclusión, construimos un asistente de compras completo por voz en español, todo dentro de Colab. El re-ranker mejora la búsqueda de forma significativa, las reglas casi duplican el éxito del agente y las garantías en el código dieron cero incumplimientos.

Muchas gracias."""),
}
