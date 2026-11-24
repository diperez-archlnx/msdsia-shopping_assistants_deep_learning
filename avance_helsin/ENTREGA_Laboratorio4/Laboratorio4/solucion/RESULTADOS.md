# Resultados: Laboratorio 4 (ejecución local de referencia)

> Hardware: RTX 5090 Laptop (24 GB) con Windows 11, Python 3.12, torch 2.11+cu128 y los mismos modelos que en Colab. Semilla 2026.
> Los audios de usuario de esta ejecución son **sintéticos** (voces de stock de XTTS). En la entrega final se sustituyen por las grabaciones reales del grupo (§8 del notebook).
> Archivos fuente: `work_local/results/*.json|csv|png`.

## 1. Datos
| | |
|---|---|
| Catálogo | 15 000 productos ESCI-es: 10 584 anotados y 4 416 distractores |
| Consultas | 400 (150 dev y 250 test), separadas por `query_id` |
| Juicios | 10 825 (E 4517 · S 3716 · C 730 · I 1862) |

## 2. Recuperación: nDCG@10 en test (250 consultas)
Ganancias E = 1, S = 0,1, C = 0,01, I = 0. Hiperparámetros ajustados **solo con dev**: w_bm25 = 0,75, rrf_k = 60, profundidad del re-ranker = 30.

| Sistema | Candidatos anotados | Catálogo completo | Latencia por consulta |
|---|---|---|---|
| BM25 (modelo base léxico) | 0,693 | 0,599 | 10 ms |
| Denso e5 | 0,726 | 0,572 | |
| Híbrido RRF | 0,726 | 0,624 | |
| Denso + re-ranker | 0,774 | 0,660 | |
| BM25 + re-ranker | 0,774 | 0,672 | |
| **Completo (RRF + re-ranker)** | **0,774** | **0,692** | 149 ms (127 ms del re-ranker) |

* Completo frente a BM25: **+0,081** en candidatos y **+0,093** en catálogo (bootstrap pareado, p < 0,001).
* **Ablación del re-ranker** (completo frente a híbrido RRF): −0,048 en candidatos y −0,068 en catálogo. Es el componente que más aporta.
* En el catálogo completo la fusión sí importa: completo 0,692 frente a 0,660 y 0,672 con un solo recuperador.

**5 aciertos**: «view2», «vestidos fiesta», «vestido calvin klein», «urna cenizas», «tv 22 pulgadas». Son consultas con la marca, el modelo o el tipo de producto en el título.

**5 fallos**:
| Consulta | Causa |
|---|---|
| «carne» | Consulta de una sola palabra y muy genérica: los productos *Exact* (carne envasada) compiten con accesorios de cocina |
| «repuesto vaso licuadora oster» | Restricción de compatibilidad: devuelve licuadoras completas, no el repuesto |
| «aspiradoras dyson sin bolsa» | Negación implícita y marca: aparecen bolsas y aspiradoras de otras marcas |
| «carpetas sin anillas» | **Negación**: «anillas» atrae justo los productos excluidos |
| «shein ropa niña» | Marca de una tienda que no aparece en los títulos |

## 3. Agente: 22 escenarios de texto
| Versión | Correctos | Incumplimientos de restricciones |
|---|---|---|
| v1 (solo el LLM con herramientas validadas) | 8/22 (36 %) | 0 |
| **v3 (final: LLM + control determinista)** | **19/22 (86,4 %)** | **0** |
| Ablación v3 sin reglas (`use_rules=False`) | 11/22 (50 %) | 0 |

* **0 incumplimientos en todas las versiones.** Las garantías de presupuesto, confirmación, idempotencia y stock están en las herramientas y en el `Store`, no en el LLM. Las reglas mejoran la **tasa de tareas completadas**, no la seguridad.
* De v1 a v3: auto-cotización y resumen generado por el código, preferencia de color, aviso de productos agotados, `referencia_ambigua`, `reemplazar_en_carrito` y aviso al LLM cuando afirma una acción que no ejecutó.
* **Aviso de sesgo**: v3 se iteró observando estos mismos escenarios. El 86 % es optimista y la ablación mide la contribución de las reglas, no la generalización.

Fallos que quedan en v3:
| Id | Qué pasó | Causa |
|---|---|---|
| S02 | No llegó a hacer el pedido del cargador | La búsqueda «cargador USB C» puso un **cable** primero, y el LLM pidió permiso en lugar de actuar |
| S04 | El evento de producto agotado encontró el carrito vacío | En el turno 1 el LLM preguntó «¿quieres que la añada?» en lugar de añadirla (exceso de cautela) |
| S12 | El color azul se guardó, pero la búsqueda no lo usó | El LLM no incorpora la preferencia de la memoria a la consulta |

## 4. Voz: 6 escenarios (S01, S02, S03, S04, S06 y S07), 20 turnos
| Escenario | Con audio | Con la transcripción correcta |
|---|---|---|
| S01 compra con presupuesto | ✅ | ✅ |
| S02 petición ambigua | ❌ | ❌ |
| S03 cambio de cantidad 3 → 5 | ✅ | ✅ |
| S04 producto agotado | ❌ | ❌ |
| S06 corrección del ASR (13 → 3) | ✅ | ✅ |
| S07 cambio de stock y confirmación repetida | ✅ | ✅ |
| **Total** | **4/6 (67 %)** | **4/6 (67 %)** |

* **ASR**: WER media de 0,005. Hay 19 de 20 turnos literales y un solo error: en S07 t3 se insertó «Ken» al final («vuelve a cotizar Ken», WER 0,09), sin efecto en la acción.
  * Errores en entidades: **0/9 en cantidades, 0/2 en importes y 0/10 en productos** (CER 0,003).
  * El log original marca 1/11 en productos, pero es un artefacto de medición: en S02 se buscaba «móvil» en el turno 1, cuando el usuario lo dice en el turno 2. Ya está corregido en `scenarios.py`.
  * Por eso los resultados con audio y con la transcripción correcta coinciden: los dos fallos son del agente (los mismos S02 y S04 del texto), no del ASR.
  * Los cambios de tilde o de puntuación («Sí, confirmó», «"Sí", confirmó») no afectan tras la normalización.
  * Con audio sintético y limpio el ASR está en su mejor caso. Con voz real cabe esperar errores en los números, y por eso existe S06.
* **S06**: se inyectó el error «tres» → «13». El usuario corrige la transcripción y se ejecuta el texto corregido: **pedido de 3, nunca de 13**.
* **S07**: el stock baja entre la cotización y la confirmación. Da `stock_insuficiente`, se recotiza, se hace **un único pedido** pese a la confirmación repetida, y el inventario queda en 0.

### Calidad del TTS (XTTS-v2 con clonación)
| Métrica | Valor |
|---|---|
| Inteligibilidad: WER de Whisper sobre la respuesta sintetizada (media y mediana) | 0,167 / 0,193 (mín. 0, máx. 0,35) |
| Semejanza con la referencia: coseno de WavLM-SV (media) | **0,984** |
| Cota superior (dos mitades de la referencia) | 0,983 |
| Cota inferior (otra voz frente a la referencia) | 0,555 |
| Solapamiento de trigramas con el texto de referencia | 0,0 (no se copia la referencia) |

La semejanza alcanza la cota superior: la voz clonada no se distingue de la de referencia para el verificador. La WER de inteligibilidad, alrededor del 17 %, se concentra en las cifras, las siglas («USB C») y los nombres de marca.

## 5. Latencia
**Carga en frío** (una vez):
| Modelo | Carga | VRAM |
|---|---|---|
| e5-base | 13,2 s | +0,56 GB |
| bge-reranker-v2-m3 | 4,1 s | +1,14 GB |
| Qwen3-8B NF4 | 23,1 s | +6,09 GB |
| Whisper large-v3-turbo | 2,9 s | +1,62 GB |
| XTTS-v2 | 11,1 s | +1,88 GB |
| WavLM-SV | 1,1 s | +0,41 GB |
| **Total** | **≈ 56 s** (más 15 s del índice BM25) | **11,7 GB**, con un pico de 17,8 GB durante la generación |

**Por turno** (20 turnos de voz):
| Etapa | Media | Mediana |
|---|---|---|
| ASR | 0,96 s (el primer turno tarda 16,4 s por el calentamiento) | 0,13 s |
| Agente: LLM | 7,55 s | 6,83 s |
| Agente: herramientas (RAG y Store) | 0,10 s | 0,02 s |
| TTS | 3,62 s | 3,55 s |
| **Total extremo a extremo** | **12,3 s** | **11,2 s** |

El **LLM domina la latencia (~62 %)**. El RAG, con el re-ranker incluido, tarda menos de 0,5 s. El turno más lento (S03 t1, 32 s) encadenó dos búsquedas y dos actualizaciones del carrito en el mismo turno. En una T4 de Colab cabe esperar entre 2 y 3 veces más en el LLM y el TTS.
