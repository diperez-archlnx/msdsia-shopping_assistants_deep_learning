# Resultados del Laboratorio 4 (generado automáticamente)

_Generado: 2026-11-25 03:55_

## Versiones y modelos

```json
{
  "python": "3.13.16",
  "torch": "2.14.1+cu130",
  "cuda": "13.0",
  "transformers": "5.22.1",
  "sentence_transformers": "5.7.0",
  "gpu": "Tesla T4",
  "coqui_tts": "0.28.0"
}
```

## Datos

```json
{
  "catalog_products": 15000,
  "annotated_products": 10584,
  "distractors": 4416,
  "dev_queries": 150,
  "test_queries": 250,
  "judgements": 10825,
  "label_distribution": {
    "E": 4517,
    "S": 3716,
    "I": 1862,
    "C": 730
  },
  "seed": 2026
}
```

## Ajuste en desarrollo (fusión)

|   w_bm25 |   rrf_k |   nDCG@10_dev |
|---------:|--------:|--------------:|
|    0.500 |  20.000 |         0.742 |
|    0.500 |  60.000 |         0.742 |
|    0.750 |  20.000 |         0.740 |
|    0.750 |  60.000 |         0.740 |
|    1.000 |  20.000 |         0.736 |
|    1.000 |  60.000 |         0.736 |
|    1.500 |  60.000 |         0.734 |
|    1.500 |  20.000 |         0.734 |

## Ajuste en desarrollo (profundidad del re-ranker)

|   rerank_depth |   nDCG@10_dev(catalogo) |
|---------------:|------------------------:|
|         10.000 |                   0.642 |
|         20.000 |                   0.675 |
|         30.000 |                   0.682 |
|         50.000 |                   0.687 |

## Recuperación en test (nDCG@10)

| sistema                            | modo       |   nDCG@10 |   Recall_E@10 |
|:-----------------------------------|:-----------|----------:|--------------:|
| BM25 (base léxica)                 | candidates |     0.693 |         0.558 |
| BM25 (base léxica)                 | catalog    |     0.599 |         0.469 |
| Denso e5                           | candidates |     0.726 |         0.570 |
| Denso e5                           | catalog    |     0.572 |         0.441 |
| Híbrido RRF (sin re-ranker)        | candidates |     0.730 |         0.579 |
| Híbrido RRF (sin re-ranker)        | catalog    |     0.611 |         0.473 |
| Denso + re-ranker (sin BM25)       | candidates |     0.777 |         0.608 |
| Denso + re-ranker (sin BM25)       | catalog    |     0.677 |         0.519 |
| BM25 + re-ranker (sin denso)       | candidates |     0.777 |         0.608 |
| BM25 + re-ranker (sin denso)       | catalog    |     0.679 |         0.515 |
| Sistema completo (RRF + re-ranker) | candidates |     0.777 |         0.608 |
| Sistema completo (RRF + re-ranker) | catalog    |     0.697 |         0.531 |

## Significancia frente a BM25

| sistema                            | modo       |   Δ vs BM25 | IC95             |     p |
|:-----------------------------------|:-----------|------------:|:-----------------|------:|
| Denso e5                           | candidates |       0.033 | [+0.010, +0.054] | 0.001 |
| Denso e5                           | catalog    |      -0.028 | [-0.059, +0.004] | 0.954 |
| Híbrido RRF (sin re-ranker)        | candidates |       0.037 | [+0.019, +0.055] | 0.000 |
| Híbrido RRF (sin re-ranker)        | catalog    |       0.012 | [-0.012, +0.038] | 0.175 |
| Denso + re-ranker (sin BM25)       | candidates |       0.083 | [+0.062, +0.106] | 0.000 |
| Denso + re-ranker (sin BM25)       | catalog    |       0.078 | [+0.052, +0.105] | 0.000 |
| BM25 + re-ranker (sin denso)       | candidates |       0.083 | [+0.061, +0.106] | 0.000 |
| BM25 + re-ranker (sin denso)       | catalog    |       0.080 | [+0.058, +0.103] | 0.000 |
| Sistema completo (RRF + re-ranker) | candidates |       0.083 | [+0.062, +0.106] | 0.000 |
| Sistema completo (RRF + re-ranker) | catalog    |       0.097 | [+0.073, +0.123] | 0.000 |

## Aciertos y fallos de recuperación

| tipo    |   query_id | consulta                      |   nDCG@10 |   nDCG@10_BM25 | top3                                                                                                                                                                                                   |   n_E |   n_cand |
|:--------|-----------:|:------------------------------|----------:|---------------:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------:|---------:|
| acierto |     108605 | view2                         |     1.000 |          0.249 | [E] Wiko View2 Pro - Smartphone con Pantalla de 6" (Dual SIM, Oc | [E] WIKO View2 Go – Smartphone con pantalla panorámica de 5,93"  | [E] WIKO View2 Go – Smartphone con pantalla panorámica de 5,93"  |     4 |       16 |
| acierto |     108385 | vestidos fiesta               |     1.000 |          0.862 | [E] Vectry Rebajas Vestidos De Fiesta Vestidos para Boda Vestido | [E] DIDK Mujer Vestido de Fiesta, Vestido Manga Larga, Vestido A | [E] Overdose Vestido De Fiesta De Noche para Las Mujeres Sexy Si |    17 |       32 |
| acierto |     108338 | vestido calvin klein mujer    |     1.000 |          0.680 | [E] Calvin Klein Monogram Stripe Ballet Dress Vestido, Blanco (B | [E] Calvin Klein - Vestido Camisero DE Manga Corta con Logo Grab | [E] Calvin Klein Jeans CK Logo Trim Ls Milano Dress, Vestido par |    19 |       40 |
| acierto |     107132 | urna cenizas pequeñas         |     1.000 |          1.000 | [E] Urna pequeña para cenizas humanas personalizadas, 10 ml, imp | [E] zootop Mini urnas de cremación para cenizas, urnas pequeñas  | [E] 3 unids pequeñas urnas Cenizas humanas, urnas de Recuerdo pa |    28 |       39 |
| acierto |     105872 | tv 22 pulgadas                |     1.000 |          0.851 | [E] Nevir TV 22PULGADAS LED Full HD - NVR - 7705-22FHD2 - N - TD | [E] LG Electronics 22TK410V-PZ - Monitor/TV de 22" LED con TDT2  | [E] TV LED 22" INFINITON Full HD (Especial 12V Caravana) Reprodu |     6 |       16 |
| fallo   |      23241 | carne                         |     0.028 |          0.209 | [C] Aobosi Picadora de Carne Eléctrica, 1200W Max, 3 in 1 Salchi | [I] Amix - Monster Beef Protein - Suplemento Alimenticio - Mejor | [C] ORBLUE Ablandador Manual de Carne de Acero Inoxidable        |     3 |       16 |
| fallo   |      87168 | repuesto vaso licuadora oster |     0.145 |          0.145 | [C] Poweka Piezas de Repuesto Compatible con Licuadora Oster Ost | [C] Oster 004902-050-000 - Base de Batidora de Vaso y Anillo de  | [C] Piezas Repuesto de Licuadora, Haofy Cuchilla de Batidoras de |     4 |       16 |
| fallo   |      10743 | aspiradoras dyson sin bolsa   |     0.165 |          0.165 | [S] Amazon Basics – Potente aspirador de cilindro sin bolsa, par | [S] Hoover Sprint Evo SE61 Aspiradora sin Bolsa de Trineo, Espec | [S] Rowenta Swift Power RO2981 Total Care, aspiradora sin bolsa, |     4 |       40 |
| fallo   |      23318 | carpetas sin anillas          |     0.206 |          0.385 | [S] Skycase - Carpeta de 6 anillas para archivadores (A5, sin pa | [S] Busquets Carpeta Anillas Recambio Luna LA VOLATIL | [I] Carpeta de Papel Kraft A4 Carpeta Anillas de Papel Kraft Car            |    16 |       40 |
| fallo   |      92458 | shein ropa niña               |     0.228 |          0.096 | [S] Sudaderas Mujer Tumblr Cortas con Capucha Chica Adolescente  | [S] Mujer Sudaderas con Capucha de Manga Larga para Adolescentes | [I] 4 Piezas de Sujetador de Camisola de Cuello V Bandeau Bralet |     1 |       40 |

## Escenarios de texto

| id   | escenario                                                               | categoría    | ok   |   turnos |   operaciones | fallos                                                                                                                                                                                       | incumplimientos   |
|:-----|:------------------------------------------------------------------------|:-------------|:-----|---------:|--------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------|
| S01  | Compra que cumple restricciones                                         | compra       | ✅   |        3 |             4 |                                                                                                                                                                                              |                   |
| S02  | Solicitud ambigua que requiere aclaración                               | aclaracion   | ✅   |        3 |             5 |                                                                                                                                                                                              |                   |
| S03  | Cambio de cantidad conservando el presupuesto                           | cambio       | ✅   |        3 |             8 |                                                                                                                                                                                              |                   |
| S04  | Producto agotado con alternativa                                        | agotado      | ✅   |        4 |             8 |                                                                                                                                                                                              |                   |
| S05  | Producto agotado sin solución                                           | agotado      | ✅   |        2 |             1 |                                                                                                                                                                                              |                   |
| S06  | Corrección de una transcripción antes de comprar                        | correccion   | ✅   |        3 |             6 |                                                                                                                                                                                              |                   |
| S07  | Cambio de stock entre cotización y confirmación + confirmación repetida | stock        | ✅   |        5 |             7 |                                                                                                                                                                                              |                   |
| S08  | Presupuesto excedido y ajuste                                           | presupuesto  | ❌   |        3 |             8 | se esperaban 1 pedidos y hay 0; 'mochila': cantidad 0 != 1                                                                                                                                   |                   |
| S09  | Dos productos con presupuesto                                           | compra       | ✅   |        3 |             7 |                                                                                                                                                                                              |                   |
| S10  | Comparación de alternativas sin compra                                  | comparacion  | ✅   |        3 |             4 |                                                                                                                                                                                              |                   |
| S11  | Atributo no verificable                                                 | atributos    | ❌   |        2 |             4 | turno 2: la respuesta no comunica /no (lo )?(puedo|se puede|podemos) (verificar|confirmar|asegurar)|descono|no (se )?(indica|especifica|menciona|aparece|consta|detalla)|no hay informacion/ |                   |
| S12  | Cambio de preferencia conservando el presupuesto                        | cambio       | ✅   |        4 |             6 |                                                                                                                                                                                              |                   |
| S13  | Orden de compra directa sin confirmación                                | confirmacion | ❌   |        2 |             2 | se esperaban 1 pedidos y hay 0; 'taza': cantidad 0 != 2                                                                                                                                      |                   |
| S14  | Cancelación tras la cotización                                          | confirmacion | ✅   |        2 |             3 |                                                                                                                                                                                              |                   |
| S15  | Cantidad mayor que el stock                                             | stock        | ✅   |        4 |             5 |                                                                                                                                                                                              |                   |
| S16  | Eliminar un producto del carrito                                        | cambio       | ✅   |        3 |             8 |                                                                                                                                                                                              |                   |
| S17  | Cambio de precio entre cotización y confirmación                        | stock        | ✅   |        4 |             6 |                                                                                                                                                                                              |                   |
| S18  | Cantidad fuera de rango                                                 | validacion   | ✅   |        1 |             2 |                                                                                                                                                                                              |                   |
| S19  | Referencia sin contexto previo                                          | aclaracion   | ✅   |        1 |             0 |                                                                                                                                                                                              |                   |
| S20  | Memoria del presupuesto durante varios turnos                           | memoria      | ✅   |        5 |             8 |                                                                                                                                                                                              |                   |
| S21  | Confirmación repetida sin duplicar                                      | confirmacion | ✅   |        3 |             4 |                                                                                                                                                                                              |                   |
| S22  | Filtro de precio máximo unitario                                        | busqueda     | ✅   |        1 |             1 |                                                                                                                                                                                              |                   |

## Resumen escenarios

```json
{
  "escenarios": 22,
  "completados_ok": 19,
  "porcentaje_ok": 86.4,
  "incumplimientos_totales": 0,
  "incumplimientos_por_tipo": {}
}
```

## Ablación de guardas deterministas

| variante                  |   porcentaje_ok |   incumplimientos_totales |
|:--------------------------|----------------:|--------------------------:|
| Sistema completo          |          86.400 |                         0 |
| Sin guardas deterministas |          45.500 |                         0 |

## Escenarios por voz vs transcripción correcta

| escenario   | título                                                                  | con ASR   | con transcripción correcta   | fallos ASR   |   pedidos finales |
|:------------|:------------------------------------------------------------------------|:----------|:-----------------------------|:-------------|------------------:|
| S01         | Compra que cumple restricciones                                         | ✅        | ✅                           |              |                 1 |
| S02         | Solicitud ambigua que requiere aclaración                               | ✅        | ✅                           |              |                 1 |
| S03         | Cambio de cantidad conservando el presupuesto                           | ✅        | ✅                           |              |                 1 |
| S04         | Producto agotado con alternativa                                        | ✅        | ✅                           |              |                 1 |
| S06         | Corrección de una transcripción antes de comprar                        | ✅        | ✅                           |              |                 1 |
| S07         | Cambio de stock entre cotización y confirmación + confirmación repetida | ✅        | ✅                           |              |                 1 |

## Errores de ASR

| escenario   |   turno | asr                                                                                                                        |   WER |   CER | corregido   |   amount_ref |   amount_err |   qty_ref |   qty_err |   product_ref |   product_err |
|:------------|--------:|:---------------------------------------------------------------------------------------------------------------------------|------:|------:|:------------|-------------:|-------------:|----------:|----------:|--------------:|--------------:|
| S01         |       1 | Hola, quiero comprar dos botellas de agua reutilizables y tengo un presupuesto de 40 euros.                                | 0.000 | 0.000 | False       |            1 |            0 |         1 |         0 |             2 |             0 |
| S01         |       2 | Me quedo con la primera opción. Prepárame la cotización.                                                                   | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S01         |       3 | «Sí», confirmó el pedido.                                                                                                  | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S02         |       1 | Necesito un cargador.                                                                                                      | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             1 |             0 |
| S02         |       2 | Es para un móvil con USB-C. Quiero solo uno punto con no tanto. Ne vale el primero que me muestres. Prepara la cotización. | 0.250 | 0.202 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S02         |       3 | Sí, confirmo.                                                                                                              | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S03         |       1 | Quiero tres cuadernos y dos bolígrafos, con un máximo de 30 euros. Elige los primeros que encuentres.                      | 0.000 | 0.000 | False       |            1 |            0 |         2 |         0 |             2 |             0 |
| S03         |       2 | Mejor que sean cinco cuadernos en lugar de tres. Prepara la cotización.                                                    | 0.000 | 0.000 | False       |            0 |            0 |         2 |         0 |             0 |             0 |
| S03         |       3 | Sí, confirmó.                                                                                                              | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S04         |       1 | Quiero dos tazas de café. La primera que encuentres está bien.                                                             | 0.000 | 0.000 | False       |            0 |            0 |         1 |         0 |             2 |             0 |
| S04         |       2 | Prepárame la cotización.                                                                                                   | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S04         |       3 | Vale, cámbiala por la alternativa que me propones y vuelve a cotizar.                                                      | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S04         |       4 | Sí, confirmo.                                                                                                              | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S06         |       1 | Quiero tres cuadernos. El primero que encuentres, y prepara la cotización.                                                 | 0.000 | 0.000 | True        |            0 |            0 |         1 |         0 |             1 |             0 |
| S06         |       2 | Sí, confirmo.                                                                                                              | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S07         |       1 | Quiero cuatro cables USB-C. El primero que encuentres. Prepárame la cotización.                                            | 0.000 | 0.000 | False       |            0 |            0 |         1 |         0 |             2 |             0 |
| S07         |       2 | «Sí, confirmo».                                                                                                            | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S07         |       3 | De acuerdo, entonces pon solo dos unidades y vuelve a cotizar.                                                             | 0.000 | 0.000 | False       |            0 |            0 |         1 |         0 |             0 |             0 |
| S07         |       4 | Sí. Confirmo.                                                                                                              | 0.000 | 0.000 | False       |            0 |            0 |         0 |         0 |             0 |             0 |
| S07         |       5 | ¿Sí? Confirmo. No.                                                                                                         | 0.500 | 0.273 | False       |            0 |            0 |         0 |         0 |             0 |             0 |

## Totales ASR

```json
{
  "WER_medio": 0.0375,
  "CER_medio": 0.023737373737373734,
  "errores_cantidad": "0/9",
  "errores_importe": "0/2",
  "errores_producto": "0/10"
}
```

## Calidad TTS

| index   |   turno |   WER_inteligibilidad |   similitud_referencia |   solapamiento_trigramas_ref |
|:--------|--------:|----------------------:|-----------------------:|-----------------------------:|
| count   |  20.000 |                20.000 |                 20.000 |                       20.000 |
| mean    |   2.300 |                 0.253 |                  0.952 |                        0.000 |
| std     |   1.174 |                 0.156 |                  0.010 |                        0.000 |
| min     |   1.000 |                 0.000 |                  0.932 |                        0.000 |
| 25%     |   1.000 |                 0.123 |                  0.945 |                        0.000 |
| 50%     |   2.000 |                 0.303 |                  0.954 |                        0.000 |
| 75%     |   3.000 |                 0.374 |                  0.960 |                        0.000 |
| max     |   5.000 |                 0.483 |                  0.968 |                        0.000 |

## Cotas de semejanza

```json
{
  "ref_mitad_vs_mitad (cota sup.)": 0.9856849908828735,
  "otra_voz_vs_ref (cota inf.)": 0.6633564829826355
}
```

## Latencia por etapa (s)

| index   |   turno |   asr_s |   agente_llm_s |   agente_herramientas_s |   agente_total_s |   tts_s |   total_s |   agente_otros_s |
|:--------|--------:|--------:|---------------:|------------------------:|-----------------:|--------:|----------:|-----------------:|
| count   |  20.000 |  20.000 |         20.000 |                  20.000 |           20.000 |  20.000 |    20.000 |           20.000 |
| mean    |   2.300 |   0.394 |         16.971 |                   0.655 |           17.652 |  10.512 |    28.595 |            0.027 |
| std     |   1.174 |   0.091 |          9.728 |                   0.971 |           10.452 |   5.193 |    14.308 |            0.015 |
| min     |   1.000 |   0.289 |          4.716 |                   0.000 |            4.724 |   2.488 |     7.592 |            0.009 |
| 25%     |   1.000 |   0.314 |         11.429 |                   0.007 |           11.745 |   7.445 |    18.016 |            0.017 |
| 50%     |   2.000 |   0.374 |         14.607 |                   0.018 |           15.594 |   9.655 |    28.851 |            0.020 |
| 75%     |   3.000 |   0.443 |         20.059 |                   0.968 |           21.030 |  14.358 |    34.702 |            0.039 |
| max     |   5.000 |   0.569 |         40.515 |                   3.315 |           43.878 |  22.342 |    66.855 |            0.057 |

## Carga de modelos

| modelo        |   carga_s |   vram_gb |   allocated_gb |   reserved_gb |   max_allocated_gb |   total_gb |
|:--------------|----------:|----------:|---------------:|--------------:|-------------------:|-----------:|
| embedder      |    14.900 |     0.560 |          0.560 |         0.580 |              0.560 |     15.640 |
| reranker      |    33.100 |     1.140 |          1.710 |         1.720 |              1.790 |     15.640 |
| llm           |   987.900 |     6.090 |          7.800 |         7.910 |              7.880 |     15.640 |
| asr           |    25.800 |     1.620 |          9.420 |         9.550 |              9.420 |     15.640 |
| tts           |    52.500 |     1.870 |         11.290 |        11.520 |             11.370 |     15.640 |
| speaker_verif |    11.200 |     0.410 |         11.690 |        11.870 |             11.690 |     15.640 |
