# Guía para grabar el video del Laboratorio 4

**Duración máxima: 20 minutos.** El video tiene cuatro bloques, uno por integrante. La demostración en vivo va **dentro** de esos 20 minutos.

| Persona | Bloque | Diapositivas | Tiempo | Qué cubre |
|---|---|---|---|---|
| **1** | Metodología | 1–5 | 0:00–4:00 | Portada y reparto, qué hace el asistente, arquitectura, datos ESCI, modelos elegidos |
| **2** | Implementación | 6–9 | 4:00–8:00 | RAG híbrido con re-ranker, agente y reglas, tienda y validaciones, memoria de la GPU |
| **3** | Demostración | 10–12 + Colab | 8:00–16:00 | Presenta la demo, la hace **en vivo en Colab** y muestra los 6 escenarios por voz |
| **4** | Resultados | 13–18 | 16:00–20:00 | Recuperación, agente y ablación, voz, latencia, aciertos y fallos, conclusión |

**Archivos (Drive → `master/deeplearning/laboratorio04/`):**
* Presentación: `Laboratorio4_presentacion_video.pptx`. **El guion de cada persona está en las notas del orador** (panel debajo de cada diapositiva; en PowerPoint: *Vista → Normal*). Cada nota empieza con `[PERSONA N · bloque · tiempo]`. Cambien «Persona 1–4» por sus nombres en la diapositiva 1.
* Notebook para la demo: `solucion/Laboratorio4_Demo_en_vivo.ipynb`.
* **No abrir ni ejecutar** `solucion/Laboratorio4_Asistente_Voz.ipynb`: es el notebook ya ejecutado que se entrega.

---

## Persona 3: preparar y hacer la demo

### Antes de grabar (≈ 25 min, sin cámara)
1. Abrir `solucion/Laboratorio4_Demo_en_vivo.ipynb` en Colab con la cuenta dueña de la carpeta.
2. *Entorno de ejecución → Cambiar tipo de entorno → GPU T4*.
3. Permitir el micrófono: candado a la izquierda de la URL → *Micrófono* → *Permitir*.
4. *Entorno de ejecución → Ejecutar todas* y autorizar Drive cuando lo pida. Tarda unos 20–25 min (casi todo es descargar el LLM).
5. Al llegar a la última celda aparece el botón rojo **⏹ Detener grabación**: ya está grabando. Hacer **una prueba corta** («Necesito un cargador» → Detener → Enter) y escribir `fin` cuando pida texto.
6. Usar **audífonos**: si la respuesta suena por parlantes, el micrófono la capta y la mete en el turno siguiente.

### Durante la grabación
1. Volver a ejecutar **solo la última celda** (Shift+Enter): la tienda se restaura y empieza limpia.
2. En cada turno: decir la frase → **Detener** → mirar la transcripción → **Enter** para aceptar (o escribir la corrección y Enter) → esperar la respuesta (~30 s) → suena la voz clonada.
3. El turno siguiente empieza a grabar enseguida: **esperar a que termine de hablar** el asistente antes de decir la siguiente frase.
4. **No cortar la espera** de al menos un turno (lo exige el enunciado). Mientras espera, comentar lo que pasa (notas de la diapositiva 11).
5. Al terminar, escribir `fin`: se imprimen la memoria del agente y los pedidos.

### Guion de frases

| Turno | Decir | Debe pasar |
|---|---|---|
| 1 | «Quiero dos botellas de agua reutilizables, mi presupuesto es de cuarenta euros.» | Busca opciones dentro del presupuesto |
| 2 | «Me quedo con la primera, prepárame la cotización.» | Añade 2 unidades y lee el total |
| 3 | «Sí, confirmo el pedido.» | Registra el pedido |
| 4 | «Necesito un cargador.» | Pregunta para qué dispositivo |
| 5 | «Es para un móvil con USB C, solo uno, el primero que muestres. Cotiza.» | Añade y cotiza |
| 6 | «Sí, confirmo.» → luego escribir `fin` | Segundo pedido y estado final |

Si falta tiempo, basta con los turnos 1–3 y 4–5. Si algo falla en vivo, mostrar en las diapositivas 12 y 15 los resultados ya medidos.

**Errores comunes:** `Permission denied` → falta permitir el micrófono. `NameError` → no se ejecutaron las celdas anteriores (usar *Ejecutar todas*).

---

## Cómo grabar el video
* **Todos en una PC:** OBS o la grabadora de Windows (Win+Alt+R), capturando micrófono y audio del sistema.
* **Cada uno en su casa:** reunión de Zoom grabada. Cada persona comparte la presentación en su turno; la Persona 3 comparte la pestaña de Colab con **«compartir sonido»** activado para que se oiga la voz clonada.
* Orden: diapositivas 1–9 → diapositiva 10 → **cambiar a Colab para la demo** → diapositivas 11–12 → diapositivas 13–18.
* Ensayen una vez con cronómetro: 4 + 4 + 8 + 4 minutos.

## Después de grabar
* Subir al formulario: la carpeta `solucion/` (o su enlace de Drive) y el video.
