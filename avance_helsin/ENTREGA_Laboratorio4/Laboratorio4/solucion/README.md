# Laboratorio 4: asistente de compras por voz

Asistente conversacional en español que:

1. **escucha** la petición (ASR Whisper),
2. **busca** en un catálogo de 15 000 productos de Amazon ESCI con un **RAG híbrido** (BM25 propio + denso e5 + RRF + cross-encoder),
3. **actúa** sobre una tienda simulada (precio, stock, carrito, cotización, pedido) mediante un **agente LLM con herramientas** y **validaciones en código**,
4. **responde por voz** con **clonación** de la voz de un integrante del grupo (XTTS-v2).

Todo se ejecuta localmente en una GPU T4 de Google Colab, sin APIs externas de inferencia.

---

## 1. Contenido de la entrega

```
solucion/
├── Laboratorio4_Asistente_Voz.ipynb   ← ejecución principal (Colab)
├── notebook_src.txt                    ← fuente del notebook (texto con separadores de celda)
├── README.md                           ← este documento (metodología, análisis, guion del video)
├── RESULTADOS.md                       ← resultados de la ejecución de referencia (el notebook genera los suyos en Drive)
├── requirements.txt
└── lab4/                               ← scripts Python (paquete)
    ├── config.py       semillas, tamaños, modelos e hiperparámetros
    ├── data.py         descarga ESCI, catálogo, consultas dev/test, qrels
    ├── textutils.py    normalización, tokenizador BM25, números en español, detección de confirmación
    ├── retrieval.py    BM25 (scipy.sparse), índice denso, re-ranker, fusión RRF, evidencias
    ├── metrics.py      nDCG@10 ESCI, recall, bootstrap pareado, WER/CER, errores de entidades
    ├── store.py        tienda SQLite: semilla, snapshot/restore, cotización, pedido atómico e idempotente
    ├── state.py        memoria estructurada de la conversación
    ├── tools.py        12 herramientas con validación + esquemas JSON para tool-calling
    ├── llm.py          Qwen3-8B en 4 bits, plantilla de chat con herramientas, parser de <tool_call>
    ├── agent.py        bucle ReAct, guardas deterministas, post-validación, texto apto para TTS
    ├── speech.py       grabación en Colab, ASR, TTS con clonación, similitud de hablante
    ├── pipeline.py     audio→ASR→agente→TTS con latencias; registro de carga y VRAM de modelos
    ├── scenarios.py    22 escenarios reproducibles con verificación automática
    └── evaluation.py   evaluación de recuperación, ablación, escenarios, voz, TTS, latencia, informe
```

## 2. Cómo ejecutarlo en Colab

1. Subir la carpeta `solucion/` a `MyDrive/master/deeplearning/laboratorio04/solucion/`.
2. Abrir `Laboratorio4_Asistente_Voz.ipynb` en Colab y elegir **Entorno de ejecución → Cambiar tipo → GPU T4**.
3. Ejecutar las celdas en orden. La primera instala `coqui-tts`, `sentence-transformers`, `bitsandbytes`, `accelerate` y `tabulate`. Torch y transformers vienen preinstalados en Colab.
4. Audios:
   * la **voz de referencia** (unos 30 s leyendo el texto mostrado) se graba por micrófono cuando el notebook la pide, salvo que ya exista `work/audios/referencia.wav`;
   * las **intervenciones de los 6 escenarios de voz** se generan en Colab con una voz de stock de XTTS si `USAR_TURNOS_SINTETICOS = True` (valor por defecto, §8), o se graban por micrófono con `False` (cada frase se muestra en pantalla).
   Los audios se guardan en `MyDrive/master/deeplearning/laboratorio04/work/audios/` y no se vuelven a pedir si ya existen. Sin micrófono, se pueden subir `.wav` con los mismos nombres (`referencia.wav`, `S01_t1.wav`, …).
5. Al terminar se escribe `RESULTADOS.md` con todas las tablas de la ejecución.

| Etapa | Tiempo aproximado en T4 |
|---|---|
| Descarga de ESCI (1,1 GB) y preparación | 3-5 min |
| Embeddings de 15 000 fichas (se cachean en Drive) | 2-3 min |
| Ajuste en dev y evaluación en test (6 sistemas × 2 modos) | 5-10 min |
| Carga del LLM en 4 bits | 3-5 min la primera vez (descarga de 16 GB), unos 1-2 min después |
| 22 escenarios de texto + ablación | 25-45 min |
| 6 escenarios de voz + repetición con transcripción correcta | 15-25 min |

**Versiones**: el notebook guarda las versiones exactas usadas (`work/results/versiones.json`) y las incluye en `RESULTADOS.md`. Se probó el diseño para `transformers ≥ 4.57` (lo exige `coqui-tts ≥ 0.28`), `sentence-transformers ≥ 4.0` (necesario para `CrossEncoder(model_kwargs=…)`) y `bitsandbytes ≥ 0.45`. Si la versión instalada de transformers no reconoce Qwen3, el notebook carga automáticamente `Qwen2.5-7B-Instruct`, que usa el mismo formato de herramientas.

---

## 3. Metodología y decisiones principales

### 3.1 Datos

| Elemento | Decisión | Por qué |
|---|---|---|
| Versión | `small_version == 1`, `product_locale == "es"` | El enunciado pide la versión reducida en español |
| Descarga | `github.com/amazon-science/esci-data/raw/main/...` | Los `.parquet` del zip son punteros Git LFS (133 bytes) |
| Lectura de productos | `pd.read_parquet(..., filters=[("product_locale","==","es")])` | El fichero ocupa 1,1 GB; filtrar al leer evita agotar la RAM |
| Consultas | 150 de `train` → **dev**; 250 de `test` → **test**; separadas por `query_id` | 400 ≥ 200 pedidas; dev para ajustar, test solo para evaluar |
| Filtro de consultas | ≥ 8 candidatos y ≥ 1 *Exact* | nDCG con IDCG > 0 y ranking no trivial |
| Catálogo | anotados de las 400 consultas (≈ 10-11k) + distractores ES reales hasta **15 000** | Todos los candidatos anotados están incluidos y la búsqueda en catálogo completo es realista |
| Escenarios | se garantizan ≥ 15 productos de cada tipo usado (botella, taza, cuaderno…) | Los escenarios son reproducibles con cualquier semilla |
| Etiquetas | `qrels.parquet` separado; el catálogo no tiene columnas de etiqueta (se comprueba con `assert`) | Las ESCI no pueden ser consultables por el agente |

### 3.2 Recuperación (RAG)

```
consulta ─► BM25 propio ───────┐
        └─► e5-base (coseno) ───┴─► RRF ponderado ─► filtros tienda ─► top-N ─► bge-reranker-v2-m3 ─► top-k + evidencia
```

* **BM25 (modelo base)**: implementación propia vectorizada. Los pesos `idf·tf(k1+1)/(tf+k1(1−b+b·dl/avgdl))` se precalculan en una matriz dispersa CSC, así cada consulta es una suma de columnas. El tokenizador quita acentos y *stopwords* y aplica *stemming* Snowball español. El título se duplica (*field boost*).
* **Denso**: `multilingual-e5-base`, con los prefijos `query:`/`passage:` del entrenamiento del modelo. El pasaje junta título, marca, color, *bullets* y descripción, recortado a 1 200 caracteres.
* **Fusión RRF**: `Σ w_i/(k + rank_i)`. Es robusta frente a escalas de puntuación distintas. Con las consultas dev se ajustan `w_bm25` y `k`.
* **Re-ranker**: un cross-encoder multilingüe solo sobre los `rerank_depth` mejores. La profundidad se elige en dev como la menor que queda a menos de 0,005 del mejor nDCG, para equilibrar calidad y latencia.
* **Fundamentación**: cada resultado lleva una *evidencia*, la frase de la ficha con más solapamiento con la consulta. El prompt obliga a apoyar las recomendaciones en ella. `verificar_atributo` devuelve **"desconocido"** si la ficha no menciona el atributo.
* **Filtros de negocio** (precio máximo y solo disponibles): se aplican de forma perezosa antes del re-ranking.

### 3.3 Agente, memoria y validaciones

* **LLM**: Qwen3-8B en 4 bits NF4, en modo no-thinking y con decodificación voraz, para que los escenarios sean reproducibles. Usa *tool-calling* nativo con `<tool_call>{json}</tool_call>`.
* **Bucle**: hasta 6 llamadas a herramientas por turno. Si se alcanza el límite, el agente debe responder sin herramientas.
* **Memoria estructurada** (`ConversationState`): presupuesto, preferencias, últimos resultados numerados («el segundo»), productos mostrados, cotización pendiente y pedidos. Se inyecta como JSON en el *system prompt* en cada paso. El historial textual se recorta a 6 turnos, pero lo importante no se pierde.
* **Reglas deterministas** (código, no LLM):
  * confirmación explícita (término afirmativo sin negación ni petición de cambio);
  * presupuesto explícito («máximo 30 euros», «presupuesto de 40 €»), con números escritos en palabras convertidos a cifras;
  * preferencia de color («color azul»), que se guarda en la memoria;
  * **control posterior al LLM** (`Agent._control`):
    * si el usuario confirmó una cotización de un turno anterior y el LLM no llamó a `confirmar_pedido`, el código la confirma;
    * si el carrito cambió, o se pidió una cotización y no la hay, el código cotiza;
    * el resumen de la cotización (líneas, subtotal, IVA, envío, total y «¿Confirmas el pedido?») lo **genera el código**, no el LLM, para que las cifras leídas por voz sean siempre las reales;
  * **corrección de acciones afirmadas**: si el LLM dice «añado…» sin haber llamado a una herramienta del carrito, se le avisa una vez y se le deja seguir;
  * todas estas reglas se desactivan con `AgentConfig.use_rules=False`, que es la ablación del §6.
* **Herramientas añadidas tras la primera evaluación**:
  * `reemplazar_en_carrito`, para cambiar un producto por otro;
  * aviso de los productos agotados más relevantes cuando `solo_disponibles` los oculta;
  * error `referencia_ambigua` si «el segundo» puede referirse a dos búsquedas del mismo turno.
* **Validaciones en las herramientas**:
  * producto mostrado previamente (evita ids alucinados);
  * cantidad entera entre 0 y 20;
  * stock suficiente (si no, error `agotado`/`stock_insuficiente` y `buscar_alternativa`);
  * aviso cuando el carrito supera el presupuesto;
  * cotización inválida si hay problemas de stock o de presupuesto.
* **Confirmación de pedido** (`confirmar_pedido` + `Store.confirm_order`):
  1. Exige una cotización vigente, mostrada en un turno **anterior** y confirmada por el usuario **en este turno**.
  2. Dentro de una transacción `BEGIN IMMEDIATE` vuelve a comprobar que el carrito coincide con lo cotizado, el stock, el precio y el presupuesto.
  3. Descuenta el inventario con `UPDATE … WHERE stock >= qty`, inserta el pedido y vacía el carrito.
  4. Cualquier fallo provoca `ROLLBACK`, así que **no quedan cambios parciales**, y la cotización pasa a `stale`.
  5. `orders.quote_id UNIQUE` garantiza la **idempotencia**: repetir la confirmación devuelve el mismo pedido.
* **Post-validación de la respuesta**: si el texto afirma un pedido que no existe, se reemplaza. El número de pedido real siempre se añade. Para el TTS se quitan los ids y el markdown y se escribe «euros».

### 3.4 Voz

* **ASR**: `whisper-large-v3-turbo` en fp16, con el idioma fijado en español. Antes de ejecutar se puede revisar y corregir la transcripción (celda de demostración y escenario S06).
* **TTS**: XTTS-v2 con los latentes del hablante **precalculados una vez** a partir de la referencia. Divide por frases (≤ 200 caracteres) y concatena con pausas de 150 ms.
* **Voz autorizada**: graba un integrante del grupo con consentimiento. El texto de referencia es distinto de todas las respuestas, y se comprueba con el solapamiento de trigramas.
* **Evaluación**:
  * inteligibilidad: WER de Whisper sobre el audio sintetizado;
  * semejanza: coseno entre x-vectors WavLM-SV, con una cota superior (dos mitades de la referencia) y una inferior (otra voz).

### 3.5 Gestión de memoria (T4: 15 GB de VRAM, unos 12,7 GB de RAM)

| Modelo | Precisión | VRAM aprox. |
|---|---|---|
| Qwen3-8B | NF4 + doble cuantización | 5,5-6,5 GB |
| Whisper large-v3-turbo | fp16 | 1,6 GB |
| XTTS-v2 | fp32 | 1,9-2,2 GB |
| bge-reranker-v2-m3 | fp16 | 1,1 GB |
| multilingual-e5-base | fp16 | 0,6 GB |
| WavLM-SV | fp32 | 0,4 GB |
| **Total** | | **≈ 11-12 GB** (margen para la caché KV) |

* `ModelRegistry` mide la VRAM incremental y el tiempo de carga de cada modelo.
* El parquet de productos se filtra al leerlo.
* Los embeddings se cachean en Drive.
* Los pesos BM25 se guardan en una matriz dispersa float32.
* El LLM usa `device_map="cuda:0"`: los *shards* se cuantizan al cargar, así que el pico de RAM es moderado.

---

## 4. Evaluación (qué mide cada celda)

| Requisito del enunciado | Dónde | Cómo |
|---|---|---|
| nDCG@10 (E = 1, S = 0,1, C = 0,01, I = 0) sobre los candidatos anotados | §3 del notebook | `metrics.ndcg_at_k`; también sobre el catálogo completo |
| Comparación con el modelo base léxico | §3 | BM25 frente a los otros 5 sistemas, bootstrap pareado con IC95 |
| Ablación de un componente | §3 y §6 | **Re-ranker** (completo frente a RRF sin re-ranker); fusión sin BM25 o sin denso; **guardas deterministas** en los mismos 22 escenarios |
| Sin ajustar con test | §3 | `tune_on_dev` solo usa `split == "dev"` |
| ≥ 20 escenarios reproducibles | §6 | 22 escenarios, `restore("base")` + `setup` determinista |
| 6 por voz con las situaciones pedidas, ≥ 3 multiturno | §8 | S01, S02, S03, S04, S06 y S07 (todos con ≥ 2 intervenciones) |
| Conservar audios, transcripciones, operaciones y estado final | §8 | `escenarios_voz.json` + `.wav` en Drive |
| Repetir con la transcripción correcta | §8 | `gold_results` y la tabla `vcmp` |
| % de escenarios correctos e incumplimientos | §6 y §8 | `scenario_table` y `violations()` |
| Errores de ASR en cantidades, importes y productos | §8 | `asr_error_table` (WER, CER, entidades) |
| Inteligibilidad y semejanza de la voz | §9 | `tts_quality` |
| Latencia por etapa, carga frente a consultas | §10 | `latency_breakdown`, `reg.load_report`, primer turno frente al resto |
| 5 aciertos y 5 fallos, causas y limitaciones | §3, §11 y la sección 5 | `error_analysis` + análisis de esta sección |

### Escenarios

| Id | Situación | Qué se verifica |
|---|---|---|
| S01 🎙️ | Compra dentro del presupuesto | 1 pedido, 2 botellas, total ≤ 40 € |
| S02 🎙️ | Petición ambigua («necesito un cargador») | Pregunta en el turno 1 sin tocar el carrito; luego 1 pedido |
| S03 🎙️ | Cambio de cantidad 3 → 5 | 5 cuadernos + 2 bolígrafos, presupuesto 30 € conservado |
| S04 🎙️ | Producto del carrito se agota antes de cotizar | Alternativa con stock; nunca se pide el agotado |
| S05 | Todo agotado, sin solución | Sin pedido; la respuesta comunica que no hay stock |
| S06 🎙️ | Corrección de la transcripción (13 → 3) | Pedido de 3, nunca de 13 |
| S07 🎙️ | El stock baja entre la cotización y la confirmación; confirmación repetida | Error `stock_insuficiente`, nueva cotización, **un único pedido**, inventario 2 − 2 = 0 |
| S08 | Presupuesto excedido | Ajuste a 1 mochila, total ≤ 30 € |
| S09 | Dos productos con presupuesto | Ratón + alfombrilla ≤ 40 € |
| S10 | Comparación sin compra | Usa `comparar_productos`, sin pedido |
| S11 | Atributo no verificable (lavavajillas) | «Desconocido» o la evidencia citada |
| S12 | Cambio de preferencia (negro → azul) | Preferencia actualizada, presupuesto 20 € conservado |
| S13 | «Compra ya sin preguntar» | No hay pedido sin confirmación explícita |
| S14 | Cancelación tras la cotización | Sin pedido |
| S15 | Cantidad mayor que el stock | Ajuste a las 3 unidades disponibles |
| S16 | Quitar un producto | Pedido solo con el cuaderno |
| S17 | Cambio de precio entre la cotización y la confirmación | `precio_modificado`, nueva cotización, total ≤ 30 € |
| S18 | Cantidad fuera de rango (50) | Ninguna línea con más de 20 |
| S19 | «Añade el segundo» sin contexto | Aclaración, carrito vacío |
| S20 | Presupuesto recordado durante 5 turnos | Total ≤ 25 € |
| S21 | Confirmación repetida | Un único pedido |
| S22 | Filtro «menos de 20 €» | Todos los resultados mostrados ≤ 20 € |

**Incumplimientos de restricciones** contados en todos los escenarios: `presupuesto_superado`, `pedido_sin_confirmacion`, `pedido_duplicado`, `stock_negativo` y `pedido_de_agotado`.

---

## 5. Análisis de aciertos, fallos y limitaciones

> Las cifras de esta sección son las de la **ejecución del notebook en Google Colab (GPU Tesla T4)** del 24 de noviembre, con la semilla 2026. Las tablas completas están en **`RESULTADOS.md`**, que el propio notebook regenera en Drive. Los turnos de usuario de los escenarios por voz de esta ejecución son sintéticos (voz de stock de XTTS); la voz de las respuestas es la clonada a partir de la grabación de referencia del grupo.

### 5.1 Recuperación
* **Modelo base léxico frente al sistema completo**: nDCG@10 en test pasa de 0,693 a **0,777** en los candidatos anotados y de 0,599 a **0,697** en el catálogo completo. En los dos casos la mejora es significativa (bootstrap pareado, p < 0,001; IC95 de la diferencia [+0,062, +0,106] y [+0,073, +0,123]).
* **Ablación**:
  * El **re-ranker** es el componente que más aporta: quitarlo (híbrido RRF solo) resta 0,047 en los candidatos (0,730) y 0,086 en el catálogo (0,611).
  * La fusión RRF solo marca diferencia en el catálogo completo (0,697 frente a 0,679 de BM25 + re-ranker y 0,677 de denso + re-ranker), donde los dos recuperadores encuentran candidatos distintos. En los candidatos anotados las tres variantes con re-ranker empatan (0,777).
  * El denso solo supera a BM25 en los candidatos (0,726 frente a 0,693), no en el catálogo (0,572 frente a 0,599): el modelo e5 confunde productos con el mismo tema y distinta función.
* **Aciertos**: «view2», «vestidos fiesta», «vestido calvin klein mujer», «urna cenizas pequeñas», «tv 22 pulgadas». Son consultas cuya marca, modelo o tipo aparece literal en el título.
* **Fallos**:
  * «carpetas sin anillas» y «aspiradoras dyson sin bolsa»: **negaciones**, el término negado atrae los productos excluidos;
  * «repuesto vaso licuadora oster»: **compatibilidad**, devuelve el aparato y no el repuesto;
  * «carne»: consulta genérica de una palabra (aparecen picadoras y ablandadores, complementos);
  * «shein ropa niña»: marca de tienda que no aparece en el texto del producto.

### 5.2 Agente
* **0 incumplimientos de restricciones** en el sistema completo y en la ablación. Las garantías (confirmación explícita, presupuesto, stock, atomicidad e idempotencia) están en las herramientas y el `Store`, así que no dependen del LLM. Los tres fallos de abajo lo muestran: el agente no completa la tarea, pero la tienda nunca queda en un estado inválido.
* **Tareas completadas**: la primera versión del agente (v1, durante el desarrollo) resolvía 8/22. Los fallos típicos eran:
  * pedir confirmación sin cotizar;
  * pedir permiso cuando el usuario ya había elegido;
  * no guardar el color;
  * ocultar en silencio los productos agotados;
  * ordinales ambiguos entre dos búsquedas;
  * no poder reemplazar un producto del carrito.

  Cada causa se resolvió con un mecanismo (§3.3) y la versión final llega a **19/22 (86,4 %)**. Sin las reglas deterministas (`use_rules=False`, ablación sobre los mismos escenarios) cae a **10/22 (45,5 %)**: el LLM solo, con las mismas herramientas, completa menos de la mitad.
* **Fallos que quedan** (en esta ejecución):
  * **S08 (presupuesto excedido y ajuste)**: ante «tres mochilas… las primeras que encuentres», el LLM añade **tres productos distintos con una unidad cada uno** en lugar de tres unidades de uno. Al pedir «entonces solo una» deja una unidad del primero pero no quita los otros dos, así que la cotización sigue en 74,97 € frente a un presupuesto de 30 €. La guarda de presupuesto impide el pedido en todos los turnos (correcto), pero la tarea queda sin completar. Causa: ambigüedad «tres X» → cantidad o número de productos.
  * **S11 (atributo no verificable)**: a «¿La primera es apta para lavavajillas?» el agente llama a `verificar_atributo`, pero luego **añade el producto al carrito y cotiza** en vez de decir que el dato no consta. Causa: la regla `CHOICE_RE` (añadida para corregir el exceso de cautela de S02 y S04) detecta «la primera» como una elección del usuario y empuja al LLM a actuar. Es un **falso positivo de una regla léxica** introducido por esa corrección.
  * **S13 (compra directa sin confirmación)**: el LLM responde «Actualizo el carrito con la taza…» pero **no llama a `actualizar_carrito`**. La autocorrección de acciones anunciadas no la detecta porque «actualizo» no está en su lista de verbos. Al confirmar, la tienda rechaza el pedido por falta de cotización (`sin_cotizacion`), como debe.
* **Escenarios que antes fallaban y ahora pasan**: S02 (petición ambigua) y S04 (producto agotado), gracias a la regla de elección y a aplicar el evento de agotado al primer producto mostrado; S12 (cambio de preferencia de color) también pasa en esta ejecución.
* **Sesgo**: las reglas se ajustaron viendo estos mismos escenarios, así que el 86 % es optimista; además, corregir S02 y S04 rompió S11. La cifra robusta es la diferencia con la ablación (+41 puntos) y los 0 incumplimientos.

### 5.3 Voz
* **Escenarios por voz: 6/6**, igual con el audio (ASR) que con la transcripción correcta, con un pedido final en cada uno.
* **ASR**: WER media de 0,038 y **0 errores en cantidades (0/9), importes (0/2) y productos (0/10)** en los 20 turnos. Los dos turnos con errores no cambian el resultado: «quiero solo uno punto con no tanto» en S02 (WER 0,25) y «¿Sí? Confirmo. No.» en S07 t5 (WER 0,50, la confirmación repetida).
* **S06** demuestra la corrección previa: el error inyectado «tres» → «13» se corrige antes de ejecutar y se piden 3.
* **S07** demuestra que la confirmación es atómica e idempotente a pesar del cambio de stock: un solo pedido aunque se confirme dos veces.
* **TTS**:
  * semejanza con la referencia de **0,952** de media (mín. 0,932), cerca de la cota superior de 0,986 (dos mitades de la misma grabación) y muy por encima de la cota inferior de 0,663 (otra voz);
  * WER de inteligibilidad de 0,25, concentrada en las cifras, las siglas («USB C») y los nombres de marca;
  * solapamiento de trigramas con el texto de la referencia: 0 (las respuestas no reutilizan ese texto).
* **Latencia** por turno en la T4: **28,6 s de media** (mediana 28,9 s; máx. 66,9 s), repartidos en ASR 0,39 s, LLM 17,0 s, herramientas 0,66 s y TTS 10,5 s. El **LLM es el cuello de botella** (≈ 60 %), seguido del TTS.
* **Memoria y carga**: con los seis modelos cargados se usan **11,7 GB de los 15,6 GB** de la T4. La carga inicial del LLM tardó 988 s porque incluye la descarga de Qwen3-8B en una sesión nueva de Colab; el resto de modelos carga en 11–53 s.

### 5.4 Limitaciones
* Catálogo estático de 15k productos y precios ficticios. No hay atributos estructurados: tallas, compatibilidades y materiales solo se conocen si aparecen en el texto.
* El nDCG sobre el catálogo completo subestima la calidad real, porque hay productos relevantes no anotados que cuentan como 0.
* La latencia no es de tiempo real: unos 29 s por turno en la T4, más del doble que los 12,3 s de la ejecución local de referencia en una RTX 5090 Laptop. El LLM en 4 bits domina el tiempo.
* Las reglas de confirmación, presupuesto, color y elección son léxicas. Tienen falsos negativos («no hay problema, confirmo» no se toma como confirmación; «actualizo» no se reconoce como acción anunciada, S13) y falsos positivos («la primera» en una pregunta se toma como elección, S11).
* Los turnos de usuario de esta ejecución son sintéticos y limpios, que son el mejor caso para el ASR. El habla espontánea y el ruido real darán más errores en los números.
* Un solo hablante de referencia, y una métrica de semejanza automática (no hay una prueba MOS con oyentes).
* XTTS-v2 tiene licencia CPML (solo uso no comercial), adecuada para el uso académico.

---

## 6. Guion del video (máximo 20 min)

| Bloque | Tiempo | Contenido | Qué mostrar |
|---|---|---|---|
| **Metodología** | 0:00-4:00 | Problema; diagrama de la arquitectura (celda 0); por qué cada modelo (tabla de la §0); datos: versión reducida es, dev/test por `query_id`, catálogo de 15k, etiquetas aisladas | Celdas 0 y 1, `summary.json` |
| **Implementación** | 4:00-8:00 | RAG híbrido (BM25 propio, RRF, re-ranker, evidencia, «desconocido»); agente (bucle, 12 herramientas, memoria JSON, guardas); tienda (transacción, idempotencia, snapshot); presupuesto de VRAM | `retrieval.py`, `tools.confirmar_pedido`, `store.confirm_order`, tabla de carga de modelos |
| **Demostración** | 8:00-16:00 | (1) Compra completa por voz con la **espera real** sin cortes (S01 o la celda en vivo); (2) un caso de aclaración (S02) o de recuperación ante falta de stock (S07: rechazo, nueva cotización, confirmación repetida sin duplicar) | Celda 12 en vivo; audios y estado final de la §8 |
| **Resultados** | 16:00-20:00 | nDCG@10 base frente a completo y ablación (gráfico); % de escenarios y incumplimientos; ASR con y sin transcripción correcta; TTS; latencia por etapa; 5 aciertos y 5 fallos; limitaciones | `ndcg_sistemas.png`, `latencia.png`, `RESULTADOS.md` |

---

## 7. Reproducibilidad

* Semilla global `SEED = 2026` (selección de consultas, distractores y tienda). El precio y el stock de cada producto dependen de `sha256(semilla:product_id)`.
* `Store.reset(seed)` regenera la tienda y `snapshot`/`restore` fijan los estados iniciales. El notebook comprueba con un hash que dos tiendas generadas con la misma semilla son idénticas.
* El LLM usa decodificación voraz. El TTS es estocástico (temperatura 0,65), pero no afecta a la lógica.
