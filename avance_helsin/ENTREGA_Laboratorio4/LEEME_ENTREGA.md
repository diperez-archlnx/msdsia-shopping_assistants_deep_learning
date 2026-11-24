# Laboratorio 4: asistente de compras por voz. Carpeta de entrega

Paquete del grupo con el código, la voz de referencia y las evidencias de las pruebas, ordenado según el enunciado.

## 1. Estructura

```
ENTREGA_Laboratorio4/
├── LEEME_ENTREGA.md                 ← este archivo
├── Laboratorio4/                    ← se sube TAL CUAL a Google Drive → MyDrive/Laboratorio4/
│   ├── solucion/                    ← CÓDIGO FUENTE (lo que se entrega en el formulario)
│   │   ├── Laboratorio4_Asistente_Voz.ipynb   ejecución principal en Colab
│   │   ├── README.md                          metodología, ejecución en Colab, análisis y guion del video
│   │   ├── RESULTADOS.md                      resultados (ejecución local de referencia)
│   │   ├── requirements.txt
│   │   ├── notebook_src.txt                   fuente del notebook
│   │   ├── lab4/                              scripts Python (datos, RAG, tienda, agente, voz, evaluación)
│   │   └── tests/                             pruebas unitarias y ejecución local por etapas
│   └── work/audios/
│       └── referencia.wav           ← voz real de referencia (versión limpia), ya en la ruta que lee el notebook
└── evidencias/
    ├── ejecucion_local_referencia/  ← respaldo de RESULTADOS.md
    │   ├── resultados/              métricas (json/csv), gráficos (ndcg_sistemas.png, latencia.png) y logs
    │   └── audios_sinteticos/       turnos de usuario sintéticos + respuestas TTS de esa ejecución
    └── voz_real/                    ← clonación con la voz real del grupo
        ├── RESULTADOS_voz_real.md   calidad de la clonación (inteligibilidad, semejanza, análisis)
        ├── referencia_limpia.wav
        ├── respuestas_con_voz_clonada/   las 20 respuestas del agente con la voz clonada
        └── calidad_tts_voz_real*.csv / resumen_voz_real*.json
```

## 2. Cómo usarla

1. Copiar la carpeta `Laboratorio4/` a **Google Drive → `MyDrive/Laboratorio4/`**.
2. Abrir `solucion/Laboratorio4_Asistente_Voz.ipynb` en Colab → **Entorno de ejecución → GPU T4**.
3. Ejecutar todas las celdas. La referencia ya está en `work/audios/referencia.wav` y el notebook no la vuelve a pedir.
   En la §8, con `USAR_TURNOS_SINTETICOS = True` (valor por defecto) los turnos de usuario que falten se generan
   con una voz de stock de XTTS; con `False` se graban por micrófono (ver §4).
4. Al terminar, el notebook escribe `RESULTADOS.md` y los resultados en `MyDrive/Laboratorio4/work/results/`.
5. Descargar el notebook **ya ejecutado** (con salidas) y el `RESULTADOS.md` nuevo, y ponerlos en `solucion/`.
6. Subir al formulario la carpeta `solucion/` y el video.

## 3. Cumplimiento del enunciado

| Requisito | Dónde | Estado |
|---|---|---|
| Datos: catálogo ≥ 5 000 productos y ≥ 200 consultas separadas por `query_id` | Notebook §1, `lab4/data.py` | ✅ 15 000 productos, 400 consultas (150 dev / 250 test) |
| Tienda simulada con semilla fija y restaurable | Notebook §4, `lab4/store.py` | ✅ |
| ASR en español | Notebook §7, `lab4/speech.py` | ✅ Whisper large-v3-turbo |
| RAG sobre el catálogo; atributos no verificables como desconocidos | Notebook §2, `lab4/retrieval.py` | ✅ BM25 + denso + RRF + re-ranker |
| Agente con herramientas: consultar, carrito, cotización, pedido | Notebook §5, `lab4/agent.py`, `lab4/tools.py` | ✅ 12 herramientas |
| Estado de la conversación y aclaraciones | `lab4/state.py` | ✅ |
| Validaciones por código; pedido atómico sin duplicados | `lab4/tools.py`, `lab4/store.py` | ✅ 0 incumplimientos |
| Respuesta hablada con voz propia clonada; textos distintos de la referencia | Notebook §7, `evidencias/voz_real/` | ✅ voz real grabada, solapamiento 0 |
| Modelo base léxico y ablación | Notebook §3 y §6, `RESULTADOS.md` §2-3 | ✅ BM25 vs. completo; ablación del re-ranker y de las reglas |
| ≥ 20 escenarios reproducibles | Notebook §6, `lab4/scenarios.py` | ✅ 22 escenarios |
| 6 escenarios por voz (≥ 3 con varias intervenciones) | Notebook §8 | ⏳ probados con audio **sintético**; falta grabar la voz real (§4) |
| Conservar audios, transcripciones, operaciones y estado final | `work/results/escenarios_voz.json` + audios | ✅ en la ejecución local; se regenera en Colab |
| Repetir los casos de voz con la transcripción correcta | Notebook §8 | ✅ |
| nDCG@10, % escenarios, incumplimientos, errores de ASR en cantidades/importes/productos | `RESULTADOS.md` §2-4 | ✅ |
| Inteligibilidad y semejanza con la voz de referencia | `RESULTADOS.md` §4, `evidencias/voz_real/RESULTADOS_voz_real.md` | ✅ |
| Latencia por etapa; carga inicial vs. consultas posteriores | Notebook §10, `RESULTADOS.md` §5 | ✅ |
| ≥ 5 aciertos y 5 fallos, causas y limitaciones | `RESULTADOS.md`, `README.md` §5, notebook §11 | ✅ |
| Instrucciones de Colab, versiones, modelos y configuración | `README.md` §2, `lab4/config.py` (versiones: `versiones.json` al ejecutar) | ✅ |
| Todo ejecutado dentro de Colab, sin APIs externas | Notebook | ⏳ falta la ejecución completa en Colab (el notebook aún no tiene salidas) |
| Video de ≤ 20 min (metodología, implementación, demostración, resultados) | Guion en `README.md` §6 | ⏳ por grabar |

## 4. Pendiente del grupo

1. **Grabar los 20 turnos de usuario** (con voz real). Se pueden grabar en la §8 del notebook poniendo
   `USAR_TURNOS_SINTETICOS = False`, o subir como `.wav` a `MyDrive/Laboratorio4/work/audios/` con estos nombres
   (los que ya existan no se regeneran; si no se graban, el notebook los genera con voz sintética):

   | Archivo | Texto |
   |---|---|
   | S01_t1.wav | Hola, quiero comprar dos botellas de agua reutilizables y tengo un presupuesto de cuarenta euros. |
   | S01_t2.wav | Me quedo con la primera opción, prepárame la cotización. |
   | S01_t3.wav | Sí, confirmo el pedido. |
   | S02_t1.wav | Necesito un cargador. |
   | S02_t2.wav | Es para un móvil con USB C, quiero solo uno. Me vale el primero que me muestres, prepara la cotización. |
   | S02_t3.wav | Sí, confirmo. |
   | S03_t1.wav | Quiero tres cuadernos y dos bolígrafos, con un máximo de treinta euros. Elige los primeros que encuentres. |
   | S03_t2.wav | Mejor que sean cinco cuadernos en lugar de tres. Prepara la cotización. |
   | S03_t3.wav | Sí, confirmo. |
   | S04_t1.wav | Quiero dos tazas de café, la primera que encuentres está bien. |
   | S04_t2.wav | Prepárame la cotización. |
   | S04_t3.wav | Vale, cámbiala por la alternativa que me propones y vuelve a cotizar. |
   | S04_t4.wav | Sí, confirmo. |
   | S06_t1.wav | Quiero tres cuadernos, el primero que encuentres, y prepara la cotización. |
   | S06_t2.wav | Sí, confirmo. |
   | S07_t1.wav | Quiero cuatro cables USB C, el primero que encuentres. Prepárame la cotización. |
   | S07_t2.wav | Sí, confirmo. |
   | S07_t3.wav | De acuerdo, entonces pon solo dos unidades y vuelve a cotizar. |
   | S07_t4.wav | Sí, confirmo. |
   | S07_t5.wav | Sí, confirmo. |

2. *(Recomendado)* `otra_voz.wav`: unos segundos de **otro integrante**, como control de la métrica de semejanza.
3. **Ejecutar el notebook completo en Colab (T4)** y reemplazar en `solucion/` el notebook (con salidas) y `RESULTADOS.md`.
4. **Grabar el video** siguiendo el guion de `README.md` §6.
5. *(Opcional)* Regrabar la referencia en un lugar más silencioso: el ruido de fondo actual (≈ -40 dB) empeora la
   inteligibilidad de la voz clonada (ver `evidencias/voz_real/RESULTADOS_voz_real.md`).

## 5. Nota sobre los resultados actuales

`RESULTADOS.md` y `evidencias/ejecucion_local_referencia/` vienen de una ejecución local de referencia (RTX 5090,
mismos modelos y semilla) con **turnos de usuario sintéticos**. `evidencias/voz_real/` mide la clonación con la voz
real del grupo sobre esas mismas respuestas. Las cifras definitivas son las que genere el notebook en Colab con
las grabaciones reales; en una T4 la latencia del LLM y del TTS será entre 2 y 3 veces mayor.
