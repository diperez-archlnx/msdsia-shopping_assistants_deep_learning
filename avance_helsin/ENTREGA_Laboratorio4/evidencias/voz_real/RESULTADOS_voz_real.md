# Voz real del grupo: referencia y clonación (XTTS-v2)

> Ejecución local de prueba con los mismos modelos del notebook (RTX 5090, Windows 11). Las 20 respuestas son las
> que generó el agente en la ejecución de referencia (`escenarios_voz.json`), resintetizadas con la voz real.
> Los turnos del **usuario** de esa ejecución siguen siendo sintéticos; se sustituyen al grabarlos (§8 del notebook).

## 1. Grabación de referencia

| | |
|---|---|
| Duración | 23,5 s (el modelo pide 6-30 s) |
| Nivel medio / pico | -22 dB / -2,1 dB (sin saturación) |
| Ruido de fondo | ≈ -40 dB, continuo (lo ideal es ≈ -60 dB) |
| Transcripción (Whisper) | «Hola, soy integrante del grupo de Laboratorio 4 de Aprendizaje Profundo. Esta grabación se usa únicamente como referencia para clonar mi voz con fines académicos. Leo este párrafo con calma en un lugar silencioso para que el modelo capture bien el timbre, el ritmo y la entonación de mi forma de hablar.» |
| WER frente al párrafo esperado | 0,019 (solo «cuatro» → «4») |

**Preprocesado** (versión limpia, la que se entrega como `referencia.wav`): filtro paso alto a 80 Hz, reducción de ruido
espectral (`afftdn`, −15 dB) y recorte de los silencios inicial y final:

`highpass=f=80,afftdn=nf=-40:nr=15:tn=1,silenceremove=start_periods=1:start_silence=0.1:start_threshold=-42dB,areverse,silenceremove=start_periods=1:start_silence=0.1:start_threshold=-42dB,areverse`

## 2. Calidad de la voz clonada (20 respuestas)

| Métrica | Grabación original | **Referencia limpia (entregada)** |
|---|---|---|
| Inteligibilidad: WER de Whisper (media / mediana) | 0,358 / 0,384 | **0,238 / 0,248** |
| Semejanza con la referencia: coseno WavLM-SV (media / mín.) | 0,936 / 0,903 | **0,955 / 0,923** |
| Cota superior (mitad vs. mitad de la referencia) | 0,991 | 0,986 |
| Cota inferior (otra voz vs. referencia) | 0,840 | 0,838 |
| Solapamiento de trigramas con el texto leído | 0,000 | 0,000 |
| Tiempo de síntesis por respuesta (media) | 7,44 s | 6,97 s |

Con la referencia sintética de la ejecución de referencia se obtuvo WER 0,167 y semejanza 0,984 (`RESULTADOS.md` §4).

## 3. Detalle por respuesta (referencia limpia)

| Escenario | Turno | WER | Semejanza | Texto (inicio) |
|---|---|---|---|---|
| S01 | 1 | 0,000 | 0,947 | Tienes tres opciones de botellas de agua reutilizable disponibles dent… |
| S01 | 2 | 0,433 | 0,956 | Te resumo la cotización: 2 × HoneyHolly Botella de Agua Acero Inoxidab… |
| S01 | 3 | 0,321 | 0,946 | Tu pedido ha sido confirmado con éxito. ¡Gracias por tu compra! Si nec… |
| S02 | 1 | 0,000 | 0,965 | ¿Qué tipo de cargador necesitas? Por ejemplo, para batería, para móvil… |
| S02 | 2 | 0,000 | 0,961 | He encontrado un cargador USB-C disponible. ¿Quieres añadirlo al carri… |
| S02 | 3 | 0,261 | 0,960 | Te resumo la cotización: 1 × Cable USB Tipo C [3 Pack a 12,99 euros; e… |
| S03 | 1 | 0,513 | 0,951 | Te resumo la cotización: 3 × Miquelrius - Cuaderno Notebook Messages, … |
| S03 | 2 | 0,282 | 0,942 | Te resumo la cotización: 5 × Miquelrius - Cuaderno Notebook Messages, … |
| S03 | 3 | 0,180 | 0,959 | Tu pedido ha sido confirmado con el número terminado en 8 1 0 7. Has c… |
| S04 | 1 | 0,261 | 0,923 | La primera taza de café encontrada es la J.AKSO - Taza de café de cerá… |
| S04 | 2 | 0,217 | 0,977 | Te resumo la cotización: 2 × J.AKSO - Taza de café de a 7,99 euros; en… |
| S04 | 3 | 0,038 | 0,947 | La alternativa propuesta es la Danolt Taza de café con leche con tapa … |
| S04 | 4 | 0,435 | 0,968 | Te resumo la cotización: 2 × Danolt Taza de café con leche a 7,99 euro… |
| S06 | 1 | 0,727 | 0,954 | Te resumo la cotización: 3 × Miquelrius - Cuaderno Notebook Messages, … |
| S06 | 2 | 0,182 | 0,954 | Tu pedido está confirmado. ¡Gracias por tu compra! Tu pedido número te… |
| S07 | 1 | 0,273 | 0,970 | Te resumo la cotización: 4 × AmazonBasics - Cable macho de USB a 6,99 … |
| S07 | 2 | 0,125 | 0,947 | El producto AmazonBasics - Cable macho de USB 2.0 no tiene suficiente … |
| S07 | 3 | 0,273 | 0,970 | Te resumo la cotización: 2 × AmazonBasics - Cable macho de USB a 6,99 … |
| S07 | 4 | 0,235 | 0,957 | ¡Hecho! Pedido registrado con número terminado en B 0 A 0, por un tota… |
| S07 | 5 | 0,000 | 0,945 | Tu pedido ya está registrado. No es necesario confirmarlo de nuevo. ¿H… |

## 4. Análisis

* **El ruido de fondo de la referencia se transfiere a la síntesis.** Con la grabación original, XTTS generó pausas
  largas rellenas de ruido (hasta 5 s en S01 t1) y respuestas 1,55 veces más largas que con la voz sintética. Limpiar
  la referencia bajó la WER de 0,358 a 0,238 y subió la semejanza de 0,936 a 0,955.
* **Los errores se concentran en las cotizaciones**: cifras con decimales, el signo «×», guiones y nombres de marca
  (S06 t1, S03 t1, S04 t4). Las respuestas conversacionales cortas salen con WER 0 (S01 t1, S02 t1, S02 t2).
* **Semejanza**: la voz clonada queda cerca de la cota superior y claramente por encima de otra voz. La cota inferior
  es alta (≈ 0,84) porque la «otra voz» es sintética; con la grabación de otro integrante sería más informativa.
* **Mejoras posibles**: regrabar la referencia en un lugar más silencioso; leer las cifras en palabras antes del TTS
  (p. ej. «8,99 euros» → «ocho con noventa y nueve euros») y quitar «×» y guiones del texto que se sintetiza.
