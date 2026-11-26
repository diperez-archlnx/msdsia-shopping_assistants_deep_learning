"""Genera las diapositivas del video del Laboratorio 4 con guion en las notas del orador."""
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION

OUT = sys.argv[1]

INK = RGBColor(0x14, 0x21, 0x3D)      # azul tinta (dominante)
AMBER = RGBColor(0xFC, 0xA3, 0x11)    # acento
TEAL = RGBColor(0x2A, 0x9D, 0x8F)     # positivo
CORAL = RGBColor(0xE7, 0x6F, 0x51)    # fallo
CARD = RGBColor(0xEE, 0xF1, 0xF6)     # fondo de tarjetas
MUTED = RGBColor(0x5B, 0x67, 0x7A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEAD, BODY = "Cambria", "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]

BLOCKS = {1: ("Metodología", "0:00–4:00"), 2: ("Implementación", "4:00–8:00"),
          3: ("Demostración", "8:00–16:00"), 4: ("Resultados", "16:00–20:00")}


def bg(slide, color):
    f = slide.background.fill
    f.solid(); f.fore_color.rgb = color


def text(slide, x, y, w, h, s, size=16, color=INK, bold=False, font=BODY, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = s if isinstance(s, list) else [s]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
        r.font.color.rgb = color; r.font.name = font
    return tb


def bullets(slide, x, y, w, h, items, size=16, color=INK, space=8):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space)
        head, rest = (it if isinstance(it, tuple) else (None, it))
        r0 = p.add_run(); r0.text = "• "; r0.font.size = Pt(size); r0.font.color.rgb = AMBER; r0.font.bold = True
        if head:
            r1 = p.add_run(); r1.text = head + " "; r1.font.bold = True
            r1.font.size = Pt(size); r1.font.color.rgb = color; r1.font.name = BODY
        r2 = p.add_run(); r2.text = rest; r2.font.size = Pt(size); r2.font.color.rgb = color; r2.font.name = BODY
    return tb


def box(slide, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None: s.line.fill.background()
    else: s.line.color.rgb = line; s.line.width = Pt(1.25)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def circle(slide, x, y, d, fill, label, size=16, color=WHITE):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid(); s.fill.fore_color.rgb = fill; s.line.fill.background(); s.shadow.inherit = False
    tf = s.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = color; r.font.name = BODY
    return s


def chip(slide, person, dark=False):
    """Etiqueta de quién presenta: motivo visual repetido (círculo numerado)."""
    blk, tm = BLOCKS[person]
    circle(slide, 10.05, 0.42, 0.42, AMBER, str(person), 14, INK)
    text(slide, 10.52, 0.43, 2.3, 0.42, f"Persona {person} · {blk}", 12, WHITE if dark else MUTED, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)


def title(slide, s, sub=None, dark=False):
    text(slide, 0.6, 0.35, 9.6, 0.8, s, 34, WHITE if dark else INK, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(slide, 0.6, 1.12, 11.8, 0.5, sub, 16, AMBER if dark else MUTED, italic=True)


def notes(slide, person, s):
    blk, tm = BLOCKS[person]
    slide.notes_slide.notes_text_frame.text = f"[PERSONA {person} · {blk.upper()} · bloque {tm}]\n\n" + s


def stat(slide, x, y, w, big, label, color=INK, bigsize=48, fill=CARD):
    box(slide, x, y, w, 1.85, fill)
    text(slide, x + 0.15, y + 0.12, w - 0.3, 0.95, big, bigsize, color, bold=True, font=HEAD, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(slide, x + 0.15, y + 1.07, w - 0.3, 0.7, label, 14, MUTED, align=PP_ALIGN.CENTER)


def style_chart(ch, colors, legend=False, maxv=None, numfmt='0.000'):
    ch.has_title = False; ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(12); ch.legend.font.color.rgb = MUTED
    ca, va = ch.category_axis, ch.value_axis
    ca.tick_labels.font.size = Pt(12); ca.tick_labels.font.color.rgb = INK
    ca.format.line.color.rgb = RGBColor(0xC9, 0xD1, 0xDC); ca.has_major_gridlines = False
    va.visible = False; va.has_major_gridlines = False
    if maxv: va.maximum_scale = maxv
    va.minimum_scale = 0
    plot = ch.plots[0]; plot.gap_width = 60; plot.has_data_labels = True
    dl = plot.data_labels; dl.font.size = Pt(12); dl.font.color.rgb = INK; dl.number_format = numfmt
    dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for s, c in zip(plot.series, colors):
        s.format.fill.solid(); s.format.fill.fore_color.rgb = c


# ============ 1. Portada ============
s = prs.slides.add_slide(BLANK); bg(s, INK)
text(s, 0.8, 1.2, 11.5, 0.5, "LABORATORIO 4 · DEEP LEARNING", 16, AMBER, bold=True)
text(s, 0.8, 1.75, 11.5, 1.6, "Asistente de compras por voz en español", 46, WHITE, bold=True, font=HEAD)
text(s, 0.8, 3.65, 11.5, 0.6, "ASR · RAG híbrido · agente con herramientas · respuesta con voz clonada · todo en Colab",
     18, RGBColor(0xC9, 0xD1, 0xDC))
for i, (n, (blk, tm)) in enumerate(BLOCKS.items()):
    x = 0.8 + i * 3.0
    box(s, x, 4.75, 2.75, 1.6, RGBColor(0x22, 0x33, 0x55))
    circle(s, x + 0.2, 4.95, 0.5, AMBER, str(n), 16, INK)
    text(s, x + 0.82, 4.95, 1.85, 0.5, f"Persona {n}", 16, WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, 5.55, 2.4, 0.4, blk, 14, AMBER, bold=True)
    text(s, x + 0.2, 5.9, 2.4, 0.35, tm, 12, RGBColor(0xC9, 0xD1, 0xDC))
notes(s, 1, """(≈30 s) Buenas. Somos el grupo [nombres de los 4 integrantes]. Presentamos el Laboratorio 4: un asistente de compras que entiende consultas habladas en español, busca productos en un catálogo real de Amazon, opera sobre una tienda simulada y responde con una voz clonada de un integrante del grupo.

Nos repartimos el video en cuatro bloques, como pide el enunciado: yo explico la metodología; [Persona 2] la implementación; [Persona 3] hace la demostración en vivo; y [Persona 4] presenta los resultados.

Todo el procesamiento corre dentro de Google Colab, en una GPU T4, sin ninguna API externa de inferencia.""")

# ============ 2. Problema ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 1)
title(s, "Qué debe hacer el asistente", "Una conversación por turnos que termina en un pedido válido")
items = [("1", "Entender la voz", "Transcribe consultas habladas en español (ASR) y permite corregir la transcripción."),
         ("2", "Buscar con evidencia", "RAG sobre 15.000 productos: recomienda solo lo que el catálogo sustenta; lo no verificable es «desconocido»."),
         ("3", "Actuar sobre la tienda", "Precios, stock, carrito, cotización y pedido, solo con confirmación explícita del usuario."),
         ("4", "Recordar y aclarar", "Conserva cantidades, presupuesto y preferencias; pregunta cuando falta información."),
         ("5", "Responder por voz", "Síntesis con clonación a partir de una grabación de referencia del grupo.")]
for i, (n, h, d) in enumerate(items):
    y = 1.85 + i * 1.02
    circle(s, 0.7, y + 0.08, 0.6, TEAL if i % 2 == 0 else INK, n, 18)
    text(s, 1.5, y, 3.4, 0.75, h, 20, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 4.9, y, 7.8, 0.75, d, 16, MUTED, anchor=MSO_ANCHOR.MIDDLE)
notes(s, 1, """(≈50 s) El enunciado pide un asistente que reciba consultas habladas, use un modelo de lenguaje con recuperación de información y ejecute acciones sobre una tienda simulada.

Concretamente, debe hacer cinco cosas. Uno: transcribir la voz en español, y permitir corregir la transcripción antes de comprar. Dos: buscar en el catálogo y sustentar cada recomendación con información recuperada; si un atributo no aparece en el texto del producto, lo trata como desconocido en lugar de inventarlo. Tres: operar la tienda —precios, existencias, carrito, cotización y pedido— y registrar el pedido solo cuando el usuario lo confirma de forma explícita. Cuatro: mantener el estado de la conversación, es decir, cantidades, presupuesto y preferencias, y pedir aclaraciones cuando algo es ambiguo. Y cinco: responder por voz con una voz propia clonada.

Lo difícil no es cada pieza por separado, sino que todo funcione junto, con garantías, dentro de los 15 GB de una T4.""")

# ============ 3. Arquitectura ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 1)
title(s, "Arquitectura del sistema", "Un turno: de la grabación del usuario a la respuesta hablada")
steps = [("Voz del\nusuario", None), ("ASR", "Whisper\nlarge-v3-turbo"), ("Agente LLM", "Qwen3-8B\n4 bits NF4"),
         ("TTS", "XTTS-v2\nclonación"), ("Voz de\nrespuesta", None)]
xs = [0.6, 3.05, 5.5, 7.95, 10.4]
for (h, d), x in zip(steps, xs):
    dark = d is None
    box(s, x, 2.05, 2.25, 1.7, INK if not dark else AMBER)
    text(s, x + 0.1, 2.15, 2.05, 0.65 if d else 1.5, h, 18, WHITE if not dark else INK, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if d:
        text(s, x + 0.1, 2.85, 2.05, 0.8, d.split("\n"), 13, RGBColor(0xC9, 0xD1, 0xDC), align=PP_ALIGN.CENTER)
for x in xs[:-1]:
    a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.27), Inches(2.72), Inches(0.18), Inches(0.36))
    a.fill.solid(); a.fill.fore_color.rgb = AMBER; a.line.fill.background()
# herramientas y memoria bajo el agente
box(s, 2.3, 4.35, 4.0, 2.3, CARD)
text(s, 2.5, 4.45, 3.6, 0.45, "Herramientas", 18, INK, bold=True)
bullets(s, 2.5, 4.95, 3.7, 1.7, ["RAG híbrido sobre el catálogo", "Tienda: carrito, cotización, pedido",
                                 "Verificación de atributos"], 14, space=4)
box(s, 6.75, 4.35, 4.3, 2.3, CARD)
text(s, 6.95, 4.45, 3.9, 0.45, "Memoria estructurada", 18, INK, bold=True)
bullets(s, 6.95, 4.95, 4.0, 1.7, ["Presupuesto, preferencias, cantidades", "Resultados numerados y cotización",
                                  "Reglas deterministas y guardas"], 14, space=4)
for x in (6.05, 7.05):   # el agente consulta herramientas y memoria
    a = s.shapes.add_shape(MSO_SHAPE.UP_DOWN_ARROW, Inches(x), Inches(3.8), Inches(0.24), Inches(0.5))
    a.fill.solid(); a.fill.fore_color.rgb = AMBER; a.line.fill.background()
notes(s, 1, """(≈60 s) Esta es la arquitectura de un turno. El usuario habla; Whisper large-v3-turbo transcribe el audio. La transcripción entra al agente, que es Qwen3-8B cargado en 4 bits.

El agente no responde de memoria: trabaja en un bucle donde decide qué herramienta llamar. Abajo a la izquierda están las herramientas: la búsqueda híbrida sobre el catálogo, las operaciones de la tienda —carrito, cotización y pedido— y la verificación de atributos. A la derecha, la memoria estructurada: el presupuesto, las preferencias, los resultados numerados que se mostraron y la cotización vigente. Esa memoria se inyecta en cada paso, así que no dependemos de que todo el historial quepa en el contexto.

Cuando el agente tiene la respuesta, XTTS-v2 la sintetiza con la voz clonada de nuestro integrante.

Una decisión central: las garantías —confirmación, presupuesto, stock— viven en el código de las herramientas y de la tienda, no en el LLM.""")

# ============ 4. Datos ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 1)
title(s, "Datos: Amazon ESCI en español", "Versión reducida para ranking, filtrada por locale «es»")
stat(s, 0.6, 1.85, 2.85, "15.000", "productos en el catálogo")
stat(s, 3.65, 1.85, 2.85, "150 · 250", "consultas dev · test", bigsize=36)
stat(s, 6.7, 1.85, 2.85, "10.825", "juicios de relevancia")
stat(s, 9.75, 1.85, 2.85, "2026", "semilla fija", AMBER)
bullets(s, 0.6, 4.1, 12.0, 3.0, [
    ("Catálogo:", "10.584 productos anotados de las consultas elegidas + 4.416 distractores, con título, descripción, atributos e identificadores."),
    ("Separación por query_id:", "split train para desarrollo y ajuste; split test solo para la evaluación final."),
    ("Etiquetas ESCI aisladas:", "E = 1, S = 0,1, C = 0,01, I = 0 para el nDCG; el agente nunca puede consultarlas."),
    ("Tienda simulada:", "precios, stock, carritos y pedidos generados con semilla fija y restaurables desde una instantánea.")], 16)
notes(s, 1, """(≈50 s) Usamos el Amazon Shopping Queries Dataset, en su versión reducida para ranking y filtrado al español.

Construimos un catálogo de 15.000 productos: 10.584 son los productos anotados de las consultas que elegimos y el resto son distractores, para que la búsqueda no sea trivial. Tenemos 150 consultas de desarrollo y 250 de evaluación, separadas por query_id: las de desarrollo vienen del split train y las de test del split test, y nunca ajustamos nada con las de test.

Las etiquetas ESCI —exacto, sustituto, complemento e irrelevante— solo se usan para calcular el nDCG con las ganancias que pide el enunciado. El agente no las ve.

La tienda simulada genera precios, existencias, carritos y pedidos con la semilla 2026, y se puede restaurar desde una instantánea, así cada escenario arranca del mismo estado.""")

# ============ 5. Modelos ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 1)
title(s, "Modelos elegidos y por qué", "Preentrenados, abiertos y dimensionados para caber juntos en una T4 de 15 GB")
rows = [("Componente", "Modelo", "VRAM", "Por qué"),
        ("Embeddings", "multilingual-e5-base", "0,56 GB", "Multilingüe y ligero; buen nivel en español"),
        ("Re-ranker", "bge-reranker-v2-m3", "1,14 GB", "Cross-encoder multilingüe: el mayor aporte en nDCG"),
        ("LLM", "Qwen3-8B (NF4)", "6,09 GB", "Llamadas a herramientas nativas; 8B en 4 bits"),
        ("ASR", "Whisper large-v3-turbo", "1,62 GB", "Calidad de large-v3 con 4 capas de decodificador"),
        ("TTS", "XTTS-v2 (Coqui)", "1,87 GB", "Español y clonación zero-shot con 6–30 s de audio"),
        ("Verificación", "WavLM-base-plus-sv", "0,41 GB", "Mide la semejanza con la voz de referencia")]
tbl = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.85), Inches(12.1), Inches(4.4)).table
for j, wdt in enumerate((2.0, 3.1, 1.3, 5.7)):
    tbl.columns[j].width = Inches(wdt)
for i, r in enumerate(rows):
    for j, v in enumerate(r):
        c = tbl.cell(i, j); c.text = v
        c.fill.solid(); c.fill.fore_color.rgb = INK if i == 0 else (CARD if i % 2 else WHITE)
        p = c.text_frame.paragraphs[0]; run = p.runs[0]
        run.font.size = Pt(15); run.font.name = BODY; run.font.bold = (i == 0 or j == 0)
        run.font.color.rgb = WHITE if i == 0 else INK
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
text(s, 0.6, 6.45, 12.1, 0.5, "Total con todo cargado: 11,7 GB de 15,6 GB en la T4 (medido en la ejecución de Colab).",
     15, MUTED, italic=True)
notes(s, 1, """(≈50 s) Estos son los seis modelos. Todos son preentrenados; no entrenamos nada desde cero, lo que el enunciado permite.

Para la búsqueda: e5-base como modelo de embeddings, multilingüe y ligero, y bge-reranker-v2-m3 como re-ranker, que, como verán en los resultados, es el componente que más mejora la búsqueda. El LLM es Qwen3-8B cargado en 4 bits: lo elegimos porque soporta llamadas a herramientas de forma nativa y en 4 bits ocupa unos 6 GB. Para la voz, Whisper large-v3-turbo transcribe casi con la calidad de large-v3 pero más rápido, y XTTS-v2 sintetiza en español clonando la voz con pocos segundos de referencia. WavLM solo se usa para medir qué tan parecida es la voz clonada.

Con todo cargado usamos 11,7 GB de los 15,6 de la T4. Con esto le paso la palabra a [Persona 2], que explica cómo lo implementamos.""")

# ============ 6. RAG ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 2)
title(s, "Recuperación: RAG híbrido con re-ranker", "Dos recuperadores complementarios, una fusión y un juez más preciso")
flow = [("Consulta", "texto del usuario\no del agente"), ("BM25 propio", "léxico: marcas,\nmodelos, cifras"),
        ("Denso e5", "semántico:\nsinónimos, paráfrasis"), ("Fusión RRF", "pesos ajustados\nen dev"),
        ("Re-ranker", "cross-encoder sobre\nlos mejores candidatos"), ("Evidencia", "título, precio,\natributos verificables")]
for i, (h, d) in enumerate(flow):
    x = 0.6 + i * 2.07
    box(s, x, 1.95, 1.85, 1.65, INK if i in (3, 4) else CARD)
    text(s, x + 0.08, 2.05, 1.69, 0.6, h, 16, WHITE if i in (3, 4) else INK, bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.08, 2.7, 1.69, 1.15, d.split("\n"), 12, RGBColor(0xC9, 0xD1, 0xDC) if i in (3, 4) else MUTED,
         align=PP_ALIGN.CENTER)
bullets(s, 0.6, 4.0, 12.1, 2.8, [
    ("Ajuste solo en desarrollo:", "el peso de BM25, la constante del RRF y la profundidad del re-ranker se eligen con las 150 consultas dev."),
    ("Profundidad del re-ranker:", "la menor que queda a menos de 0,005 del mejor nDCG en dev, para equilibrar calidad y latencia."),
    ("Atributos no verificables:", "si un dato no aparece en el texto del producto, la herramienta lo devuelve como «desconocido»."),
    ("Filtros duros por código:", "precio máximo y solo disponibles se aplican sobre la tienda, no se dejan al LLM.")], 16)
notes(s, 2, """(≈60 s) Gracias. Empiezo por la recuperación, que es la R de RAG.

Combinamos dos recuperadores. BM25, que implementamos nosotros, es bueno con coincidencias literales: marcas, modelos, cifras como «22 pulgadas». El recuperador denso con e5 capta el significado, sinónimos y paráfrasis. Los fusionamos con Reciprocal Rank Fusion, con pesos que ajustamos solo con las consultas de desarrollo.

Sobre los mejores candidatos de la fusión aplicamos un re-ranker cross-encoder, que lee la consulta y el producto juntos y los reordena con mucha más precisión. La profundidad del re-ranker es la menor que queda a menos de 0,005 del mejor nDCG en desarrollo, para no pagar latencia de más.

Al agente le devolvemos evidencia: título, precio y atributos que aparecen en el texto. Si el usuario pregunta algo que el catálogo no dice, la herramienta responde «desconocido». Y los filtros duros, como precio máximo o solo disponibles, se aplican en código.""")

# ============ 7. Agente ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 2)
title(s, "Agente: LLM + herramientas + memoria", "El LLM decide qué hacer; el código garantiza que lo hecho sea válido")
box(s, 0.6, 1.85, 5.85, 4.95, CARD)
text(s, 0.85, 2.0, 5.4, 0.5, "Bucle por turno", 20, INK, bold=True)
loop = ["El LLM recibe el mensaje + la memoria en JSON", "Propone una llamada a herramienta",
        "El código la valida y la ejecuta", "El resultado vuelve al LLM (máx. 6 pasos)", "Respuesta final al usuario"]
for i, l in enumerate(loop):
    y = 2.65 + i * 0.8
    circle(s, 0.9, y, 0.5, AMBER, str(i + 1), 14, INK)
    text(s, 1.55, y - 0.03, 4.7, 0.56, l, 16, INK, anchor=MSO_ANCHOR.MIDDLE)
box(s, 6.85, 1.85, 5.85, 4.95, INK)
text(s, 7.1, 2.0, 5.4, 0.5, "Reglas deterministas", 20, AMBER, bold=True)
bullets(s, 7.1, 2.6, 5.4, 4.1, [
    ("Confirmación explícita:", "solo «sí, confirmo» y similares habilitan el pedido."),
    ("Presupuesto y color:", "se detectan por regla y quedan en la memoria."),
    ("Cotización e importes:", "el resumen con cifras lo genera el código, no el LLM."),
    ("Elección del usuario:", "si ya eligió («la primera»), se pide al LLM que actúe."),
    ("Autocorrección:", "si anuncia una acción que no ejecutó, se le pide ejecutarla.")], 15, WHITE, space=6)
notes(s, 2, """(≈60 s) El agente funciona como un bucle. En cada paso, el LLM recibe el mensaje del usuario junto con la memoria estructurada en JSON, y propone una llamada a herramienta. El código valida esa llamada, la ejecuta y devuelve el resultado al LLM, hasta seis pasos por turno, y al final el LLM redacta la respuesta.

A la derecha están las reglas deterministas que añadimos sobre el LLM. La confirmación del pedido solo se acepta si el usuario la dice de forma explícita. El presupuesto y el color se detectan por regla y se guardan en la memoria, para que no se pierdan entre turnos. Los importes que se le leen al usuario los genera el código, así nunca hay una cifra inventada. Y hay dos correcciones de comportamiento: si el usuario ya eligió un producto y el LLM solo pregunta, se le pide que actúe; y si el LLM dice que añadió algo al carrito pero no llamó a la herramienta, se le pide que lo haga.

En la ablación verán cuánto aportan estas reglas.""")

# ============ 8. Tienda ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 2)
title(s, "Tienda simulada y validaciones", "Las garantías viven en el código: el LLM no puede saltárselas")
cards = [("Cantidades y presupuesto", "Se validan en cada operación del carrito y al cotizar."),
         ("Revalidación al confirmar", "Se vuelven a comprobar precio y stock justo antes del pedido."),
         ("Transacción atómica", "Pedido e inventario cambian juntos o no cambian: sin cambios parciales."),
         ("Idempotencia", "Confirmar dos veces la misma cotización no duplica el pedido."),
         ("Sin confirmación, no hay pedido", "La herramienta rechaza pedidos sin cotización vigente ni «sí» explícito."),
         ("Restaurable", "Instantánea «base» con semilla fija: cada escenario parte del mismo estado.")]
for i, (h, d) in enumerate(cards):
    col, row = i % 3, i // 3
    x, y = 0.6 + col * 4.1, 1.9 + row * 2.45
    box(s, x, y, 3.85, 2.2, CARD)
    circle(s, x + 0.25, y + 0.25, 0.5, TEAL, "✓", 16)
    text(s, x + 0.9, y + 0.22, 2.85, 0.6, h, 17, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, y + 0.95, 3.4, 1.15, d, 15, MUTED)
notes(s, 2, """(≈50 s) La tienda simulada es donde ponemos las garantías que pide el enunciado.

Cantidades, presupuesto y existencias se validan en código en cada operación. Al confirmar, se vuelven a comprobar precio y stock, porque pueden cambiar entre la cotización y la confirmación. El pedido es una transacción atómica: o se actualizan el pedido y el inventario juntos, o no cambia nada. Es idempotente: si el usuario confirma dos veces, no se duplica el pedido. Y la herramienta de confirmar rechaza cualquier pedido sin cotización vigente o sin un «sí» explícito.

Por último, la tienda se restaura desde una instantánea con semilla fija, lo que hace los escenarios reproducibles. El resultado es que, en todos los escenarios, incluida la ablación sin reglas, tuvimos cero incumplimientos de restricciones.""")

# ============ 9. Memoria GPU ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 2)
title(s, "Gestión de memoria en la T4", "Seis modelos cargados a la vez en 11,7 GB de 15,6 GB")
cd = CategoryChartData()
cd.categories = ["e5", "Re-ranker", "Qwen3-8B", "Whisper", "XTTS-v2", "WavLM"]
cd.add_series("VRAM acumulada (GB)", (0.56, 1.71, 7.80, 9.42, 11.29, 11.69))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.8), Inches(7.4), Inches(5.0), cd)
ch = gf.chart; style_chart(ch, [INK], maxv=15.6, numfmt='0.0" GB"')
ch.has_title = True; ch.chart_title.text_frame.text = "Memoria acumulada al cargar cada modelo"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = MUTED
bullets(s, 8.3, 2.0, 4.4, 4.8, [
    ("LLM en 4 bits NF4:", "8B parámetros en unos 6 GB."),
    ("Prefill por bloques:", "prompts largos en trozos de 1.024 tokens para acotar picos."),
    ("Registro de modelos:", "cada modelo se carga una sola vez y se reutiliza."),
    ("Medición:", "carga, VRAM y picos se reportan en el notebook.")], 16)
notes(s, 2, """(≈50 s) El enunciado pide justificar los modelos y gestionar la memoria disponible. Este gráfico muestra la memoria acumulada en la GPU a medida que cargamos cada modelo en Colab: el LLM es el que más ocupa, unos 6 GB, porque lo cargamos en 4 bits; sin cuantizar necesitaría unos 16 GB y no cabría.

Además, procesamos los prompts largos por bloques de 1.024 tokens para acotar los picos de memoria, y un registro de modelos garantiza que cada uno se carga una sola vez. Con los seis cargados llegamos a 11,7 GB de 15,6, con margen.

Ahora [Persona 3] nos muestra el asistente funcionando.""")

# ============ 10. Demo: plan ============
s = prs.slides.add_slide(BLANK); bg(s, INK); chip(s, 3, dark=True)
title(s, "Demostración en vivo", "Entrada y respuesta por voz, con la espera real de cada turno", dark=True)
for i, (h, d) in enumerate([("Caso 1 · Compra completa", "Búsqueda con presupuesto → elección → cotización → confirmación → pedido registrado."),
                            ("Caso 2 · Aclaración o recuperación", "Petición ambigua que obliga a preguntar, o cambio de stock entre cotización y confirmación.")]):
    x = 0.6 + i * 6.15
    box(s, x, 1.95, 5.9, 2.4, RGBColor(0x22, 0x33, 0x55))
    circle(s, x + 0.3, 2.2, 0.6, AMBER, str(i + 1), 20, INK)
    text(s, x + 1.1, 2.2, 4.6, 0.6, h, 20, WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.3, 3.0, 5.4, 1.2, d, 16, RGBColor(0xC9, 0xD1, 0xDC))
text(s, 0.6, 4.75, 12.1, 0.5, "Qué observar en pantalla", 18, AMBER, bold=True)
bullets(s, 0.6, 5.3, 12.1, 1.8, [
    "La transcripción del ASR, que se puede corregir antes de ejecutar.",
    "Las herramientas que llama el agente y el estado del carrito.",
    "Los tiempos por etapa (ASR, LLM, herramientas, TTS) y la respuesta con la voz clonada."], 16, WHITE, space=4)
notes(s, 3, """(≈40 s) Gracias. Ahora vamos al notebook en Colab, sección 12, «Demostración en vivo». Voy a mostrar dos casos: primero, una compra completa por voz, desde la búsqueda hasta el pedido registrado; segundo, un caso de aclaración —una petición ambigua— o de recuperación ante un cambio de stock.

Fíjense en tres cosas: la transcripción del ASR, que puedo corregir antes de que se ejecute; las herramientas que llama el agente; y los tiempos de cada etapa. No vamos a cortar la espera: el enunciado pide ver al menos una interacción completa con su espera real, y en una T4 cada turno tarda entre 10 y 30 segundos.

GUÍA DE PREPARACIÓN (no leer en voz alta):
1. Antes de grabar, abrir el notebook en Colab con GPU T4, permitir el micrófono (candado junto a la URL → Micrófono → Permitir) y ejecutar todo hasta la sección 11 (unos 90 min la primera vez).
2. Iniciar la grabación de pantalla con audio del sistema (para que se oiga la voz clonada).
3. Ejecutar solo la celda de la sección 12. Por cada turno: pulsar grabar, hablar, Enter para aceptar la transcripción (o escribir la corrección). Escribir «fin» para terminar.""")

# ============ 11. Demo: guion de frases ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 3)
title(s, "Guion de la demostración", "Frases sugeridas para decir al micrófono, turno por turno")
rows = [("Turno", "Qué decir", "Qué debe hacer el asistente"),
        ("1", "«Quiero dos botellas de agua reutilizables, mi presupuesto es de cuarenta euros.»", "Busca y muestra opciones dentro del presupuesto"),
        ("2", "«Me quedo con la primera, prepárame la cotización.»", "Añade 2 unidades y lee la cotización con el total"),
        ("3", "«Sí, confirmo el pedido.»", "Registra el pedido y actualiza el inventario"),
        ("4", "«Necesito un cargador.»", "Pregunta para qué dispositivo o tipo de conector"),
        ("5", "«Es para un móvil con USB C, solo uno, el primero que muestres. Cotiza.»", "Añade el cargador y cotiza"),
        ("6", "«Sí, confirmo.»  Luego escribir «fin».", "Segundo pedido; muestra el estado final de la tienda")]
tbl = s.shapes.add_table(len(rows), 3, Inches(0.6), Inches(1.85), Inches(12.1), Inches(4.9)).table
for j, wdt in enumerate((1.0, 6.4, 4.7)):
    tbl.columns[j].width = Inches(wdt)
for i, r in enumerate(rows):
    for j, v in enumerate(r):
        c = tbl.cell(i, j); c.text = v
        c.fill.solid(); c.fill.fore_color.rgb = INK if i == 0 else (CARD if i in (1, 2, 3) else WHITE)
        run = c.text_frame.paragraphs[0].runs[0]
        run.font.size = Pt(15); run.font.name = BODY; run.font.bold = (i == 0)
        run.font.color.rgb = WHITE if i == 0 else INK
        if j == 0 and i > 0:
            c.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
text(s, 0.6, 6.85, 12.1, 0.4, "Turnos 1–3: caso de compra completa · Turnos 4–6: caso de aclaración", 14, MUTED, italic=True)
notes(s, 3, """(≈6 min en Colab; esta diapositiva es la guía del presentador) Vuelvo a Colab y ejecuto la celda de la sección 12.

CASO 1 — COMPRA (turnos 1 a 3). Digo la primera frase. Mientras procesa, comento: «Whisper transcribe, el agente llama a buscar_productos con el precio máximo, y el re-ranker ordena los candidatos». Cuando responda, digo la segunda: «Me quedo con la primera, prepárame la cotización». Comento que el resumen con los importes lo genera el código, por eso las cifras son exactas. Tercera frase: «Sí, confirmo el pedido». Señalo que el pedido quedó registrado y que, sin ese sí explícito, la tienda lo habría rechazado.

CASO 2 — ACLARACIÓN (turnos 4 a 6). «Necesito un cargador»: es ambiguo, así que el asistente debe preguntar antes de tocar el carrito. Respondo con el tipo de conector y la cantidad, y confirmo.

Al terminar escribo «fin»: se imprimen la memoria del agente y los pedidos de la sesión.

SI ALGO FALLA EN VIVO: mostrar la sección 8 ya ejecutada (escenarios S01 y S02 o S07 por voz), reproducir con el reproductor de la celda el audio del usuario y la respuesta clonada, y leer los tiempos medidos. Si el micrófono no funciona: candado de la URL → Micrófono → Permitir, y volver a ejecutar solo la celda 12.""")

# ============ 12. Escenarios por voz ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 3)
title(s, "Las seis situaciones por voz", "Evaluadas con audio y repetidas con la transcripción correcta")
sc = [("S01", "Compra que cumple las restricciones y termina en pedido"), ("S02", "Solicitud ambigua que requiere aclaración"),
      ("S03", "Cambio de cantidad conservando el presupuesto"), ("S04", "Producto agotado: se propone una alternativa"),
      ("S06", "Corrección de la transcripción antes de comprar"), ("S07", "Cambio de stock entre cotización y confirmación, sin duplicar")]
for i, (k, d) in enumerate(sc):
    col, row = i % 2, i // 2
    x, y = 0.6 + col * 6.15, 1.9 + row * 1.5
    box(s, x, y, 5.9, 1.25, CARD)
    circle(s, x + 0.25, y + 0.3, 0.65, TEAL, "✓", 20)
    text(s, x + 1.1, y + 0.12, 1.0, 0.5, k, 18, INK, bold=True)
    text(s, x + 1.1, y + 0.55, 4.65, 0.65, d, 15, MUTED)
box(s, 0.6, 6.45, 12.1, 0.75, INK)
text(s, 0.8, 6.5, 11.7, 0.65, "6/6 con el audio y 6/6 con la transcripción correcta: un pedido final en cada escenario", 18,
     WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
notes(s, 3, """(≈1 min) Además de la demo en vivo, el notebook evalúa de forma reproducible las seis situaciones por voz que pide el enunciado: la compra que termina en pedido, la solicitud ambigua, el cambio de cantidad conservando el presupuesto, el producto agotado, la corrección de una transcripción —donde inyectamos un error de ASR, «tres» se transcribe como «13», y se corrige antes de comprar— y el cambio de stock entre la cotización y la confirmación, confirmando dos veces sin duplicar el pedido.

Todas tienen dos o más intervenciones del usuario. Para separar los errores del ASR de los del agente, repetimos cada caso con la transcripción correcta como entrada. Resultado: seis de seis en las dos variantes. Guardamos los audios, las transcripciones, las operaciones y el estado final de la tienda.

[Persona 4] presenta ahora los resultados.""")

# ============ 13. Recuperación ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 4)
title(s, "Recuperación: +0,084 de nDCG@10", "Frente a BM25 en 250 consultas de test · diferencia significativa (bootstrap pareado, p < 0,001)")
cd = CategoryChartData()
cd.categories = ["BM25 (base)", "Denso e5", "Híbrido RRF", "Sistema completo"]
cd.add_series("Candidatos anotados", (0.693, 0.726, 0.730, 0.777))
cd.add_series("Catálogo completo", (0.599, 0.572, 0.611, 0.697))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75), Inches(8.0), Inches(5.3), cd)
style_chart(gf.chart, [INK, AMBER], legend=True, maxv=0.95)
stat(s, 9.0, 1.9, 3.7, "−0,047", "nDCG sin el re-ranker\n(ablación, candidatos)", CORAL, 44)
stat(s, 9.0, 4.0, 3.7, "−0,086", "sin el re-ranker en el\ncatálogo completo", CORAL, 44)
text(s, 9.0, 6.05, 3.7, 0.9, "El re-ranker es el componente que más aporta.", 14, MUTED, italic=True)
notes(s, 4, """(≈50 s) Gracias. Empiezo por la recuperación, medida con nDCG@10 en las 250 consultas de test, con las ganancias del enunciado.

El modelo base léxico, BM25, logra 0,693 sobre los candidatos anotados. El sistema completo —fusión híbrida más re-ranker— llega a 0,777, una mejora de 0,084, significativa con p menor a 0,001. Sobre el catálogo completo, que es más difícil, pasa de 0,599 a 0,697.

La ablación muestra qué aporta cada pieza: quitar el re-ranker resta 0,047 en candidatos y 0,086 en el catálogo; es el componente más valioso. El denso solo supera a BM25 sobre los candidatos, no sobre el catálogo completo, porque e5 confunde productos del mismo tema con distinta función; por eso conviene la fusión.""")

# ============ 14. Agente ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 4)
title(s, "Agente: escenarios y ablación", "22 escenarios de texto, con y sin las reglas deterministas")
stat(s, 0.6, 1.9, 3.85, "86,4 %", "sistema completo\n19 de 22 escenarios", TEAL, 54)
stat(s, 4.75, 1.9, 3.85, "45,5 %", "sin reglas deterministas\n10 de 22 escenarios", CORAL, 54)
stat(s, 8.9, 1.9, 3.8, "0", "incumplimientos de restricciones\nen las dos variantes", INK, 54)
bullets(s, 0.6, 4.2, 12.1, 2.9, [
    ("Las reglas aportan +41 puntos:", "el LLM solo, con las mismas herramientas, completa menos de la mitad de las tareas."),
    ("Las garantías no dependen del LLM:", "incluso sin reglas no hubo pedidos sin confirmación, duplicados ni presupuestos superados."),
    ("Sesgo declarado:", "las reglas se ajustaron mirando estos escenarios; el 86 % es optimista. Lo robusto es la diferencia y los 0 incumplimientos.")], 16)
notes(s, 4, """(≈50 s) Evaluamos 22 escenarios operativos de texto, con estados iniciales reproducibles. El sistema completo resuelve 19 de 22, un 86,4 %.

Para la ablación a nivel de sistema repetimos exactamente los mismos escenarios desactivando las reglas deterministas, de modo que el LLM decide solo. Cae a 10 de 22, un 45,5 %: las reglas aportan unos 41 puntos.

Lo más importante es la tercera cifra: cero incumplimientos de restricciones en las dos variantes. Aunque el LLM se equivoque, la tienda nunca registra un pedido sin confirmación, duplicado o fuera de presupuesto, porque esas garantías están en el código.

Somos honestos con un sesgo: ajustamos las reglas mirando estos escenarios, así que el 86 % es optimista; la cifra robusta es la diferencia con la ablación y los cero incumplimientos.""")

# ============ 15. Voz ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 4)
title(s, "Voz: reconocimiento y síntesis", "20 turnos de usuario en 6 escenarios")
stat(s, 0.6, 1.9, 2.85, "0,038", "WER medio del ASR", INK, 44)
stat(s, 3.65, 1.9, 2.85, "0", "errores en cantidades,\nimportes y productos", TEAL, 44)
stat(s, 6.7, 1.9, 2.85, "0,952", "semejanza de la voz\nclonada (coseno)", INK, 44)
stat(s, 9.75, 1.9, 2.95, "0,25", "WER de inteligibilidad\nde la voz clonada", CORAL, 44)
box(s, 0.6, 4.15, 12.1, 1.45, CARD)
text(s, 0.85, 4.25, 11.6, 0.45, "Semejanza en contexto (WavLM, coseno)", 16, INK, bold=True)
# barra de cotas
x0, x1 = 0.85, 12.45
def pos(v): return x0 + (v - 0.6) / 0.4 * (x1 - x0)
bar = box(s, x0, 4.85, x1 - x0, 0.18, RGBColor(0xC9, 0xD1, 0xDC), shape=MSO_SHAPE.RECTANGLE)
for v, lab, col in ((0.663, "otra voz 0,663", CORAL), (0.952, "voz clonada 0,952", TEAL), (0.986, "misma persona 0,986", INK)):
    circle(s, pos(v) - 0.13, 4.81, 0.26, col, "", 8)
    text(s, pos(v) - 1.2, 4.42 if v == 0.952 else 5.1, 2.4, 0.4, lab, 13, col, bold=True, align=PP_ALIGN.CENTER)
bullets(s, 0.6, 5.85, 12.1, 1.4, [
    ("ASR:", "los turnos de esta evaluación son sintéticos (audio limpio): es el mejor caso; con habla real habrá más errores."),
    ("TTS:", "los errores de inteligibilidad se concentran en cifras, siglas («USB C») y marcas.")], 15, space=4)
notes(s, 4, """(≈45 s) En voz medimos las dos direcciones. El reconocimiento tuvo un WER medio de 0,038 y, lo que más importa para comprar, cero errores en cantidades, importes y productos en los 20 turnos. Una aclaración: en esta evaluación los turnos del usuario son sintéticos, audio limpio, que es el mejor caso para el ASR; con habla espontánea esperamos más errores, sobre todo en los números.

Para la voz clonada medimos la semejanza con x-vectors de WavLM: 0,952, muy cerca de la cota superior de 0,986, que es comparar dos mitades de la misma grabación, y muy lejos de 0,663, que es otra voz. La inteligibilidad, medida transcribiendo el audio sintetizado, tiene un WER de 0,25, concentrado en cifras, siglas y marcas. También comprobamos que ninguna respuesta reutiliza el texto de la grabación de referencia.""")

# ============ 16. Latencia ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 4)
title(s, "Latencia por turno en la T4", "Desde que termina la grabación hasta que la respuesta puede reproducirse")
cd = CategoryChartData()
cd.categories = ["ASR", "Agente: LLM", "Herramientas", "TTS"]
cd.add_series("Segundos (media)", (0.39, 16.97, 0.66, 10.51))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.8), Inches(7.6), Inches(4.6), cd)
style_chart(gf.chart, [INK], maxv=20, numfmt='0.0" s"')
gf.chart.plots[0].vary_by_categories = False
gf.chart.category_axis.reverse_order = True
stat(s, 8.6, 1.9, 4.1, "28,6 s", "total medio por turno\n(mediana 28,9 s)", INK, 48)
bullets(s, 8.6, 4.05, 4.1, 3.0, [
    ("El LLM es el cuello de botella:", "≈ 60 % del tiempo."),
    ("Carga inicial aparte:", "se mide una sola vez y no entra en el turno."),
    ("No es tiempo real,", "y el enunciado no lo exige.")], 15, space=6)
notes(s, 4, """(≈40 s) La latencia se mide desde que termina la grabación hasta que la respuesta puede reproducirse, desglosada por etapa. En la T4, un turno tarda 28,6 segundos de media. La transcripción tarda menos de medio segundo y las herramientas, incluida la búsqueda, menos de uno. El LLM se lleva unos 17 segundos, cerca del 60 %, y la síntesis de voz unos 10.

La carga inicial de los modelos se mide aparte, una sola vez, como pide el enunciado. No es tiempo real, que el enunciado no exige; la mejora más directa sería un LLM más pequeño o una GPU más rápida: en una RTX 5090 el mismo sistema tardaba unos 12 segundos por turno.""")

# ============ 17. Aciertos y fallos ============
s = prs.slides.add_slide(BLANK); bg(s, WHITE); chip(s, 4)
title(s, "Aciertos y fallos", "Qué funcionó, qué no y por qué")
box(s, 0.6, 1.85, 5.95, 4.6, CARD)
circle(s, 0.85, 2.05, 0.55, TEAL, "✓", 18)
text(s, 1.55, 2.05, 4.8, 0.55, "Aciertos", 20, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
bullets(s, 0.85, 2.8, 5.55, 4.2, [
    ("Búsqueda literal:", "«view2», «tv 22 pulgadas», «vestido calvin klein» → nDCG 1,0."),
    ("S06:", "el error de ASR «tres» → «13» se corrige antes de comprar."),
    ("S07:", "cambio de stock detectado; confirmar dos veces no duplica."),
    ("S02 y S04:", "aclaración y producto agotado, resueltos por voz."),
    ("Garantías:", "0 incumplimientos en todos los escenarios.")], 17, space=6)
box(s, 6.75, 1.85, 5.95, 4.6, CARD)
circle(s, 7.0, 2.05, 0.55, CORAL, "✗", 18)
text(s, 7.7, 2.05, 4.8, 0.55, "Fallos y causas", 20, INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
bullets(s, 7.0, 2.8, 5.55, 4.2, [
    ("Negaciones:", "«carpetas sin anillas» trae carpetas con anillas."),
    ("Compatibilidad:", "«repuesto vaso licuadora» devuelve la licuadora."),
    ("S08:", "«tres mochilas» → tres productos distintos; nunca baja del presupuesto."),
    ("S11:", "«¿la primera es apta…?» se toma como elección (falso positivo de una regla)."),
    ("S13:", "el LLM dice «actualizo el carrito» pero no llama a la herramienta.")], 17, space=6)
notes(s, 4, """(≈45 s) El enunciado pide analizar al menos cinco aciertos y cinco fallos; aquí van los principales, y el análisis completo está en el README.

Aciertos: las consultas con marca o modelo literal, como «view2» o «tv 22 pulgadas», alcanzan nDCG perfecto; la corrección de transcripción de S06; el cambio de stock de S07 sin duplicar pedidos; y la aclaración y el producto agotado, que en la versión anterior fallaban y ahora pasan.

Fallos: en búsqueda, las negaciones —«sin anillas» atrae carpetas con anillas— y la compatibilidad —buscar un repuesto devuelve el aparato—. En el agente, S08 interpreta «tres mochilas» como tres productos distintos; S11 es un efecto secundario de una de nuestras reglas, que toma «la primera» dentro de una pregunta como una elección; y en S13 el LLM anuncia que actualiza el carrito sin hacerlo. En los tres casos la tienda impidió un pedido inválido.""")

# ============ 18. Cierre ============
s = prs.slides.add_slide(BLANK); bg(s, INK); chip(s, 4, dark=True)
title(s, "Limitaciones y conclusión", dark=True)
box(s, 0.6, 1.5, 5.95, 4.9, RGBColor(0x22, 0x33, 0x55))
text(s, 0.85, 1.65, 5.5, 0.5, "Limitaciones", 20, AMBER, bold=True)
bullets(s, 0.85, 2.25, 5.5, 4.7, [
    "Catálogo estático, precios ficticios y sin atributos estructurados.",
    "Reglas léxicas: falsos positivos y negativos (S11, S13).",
    "Unos 29 s por turno en la T4: no es tiempo real.",
    "Turnos de usuario sintéticos en la evaluación; un solo hablante de referencia.",
    "Semejanza de voz automática, sin prueba con oyentes (MOS)."], 17, WHITE, space=6)
box(s, 6.75, 1.5, 5.95, 4.9, RGBColor(0x22, 0x33, 0x55))
text(s, 7.0, 1.65, 5.5, 0.5, "Conclusión", 20, AMBER, bold=True)
bullets(s, 7.0, 2.25, 5.5, 4.7, [
    "Asistente completo por voz en español, todo dentro de Colab y sin APIs.",
    "El re-ranker mejora la búsqueda de forma significativa (+0,084 nDCG@10).",
    "Las reglas deterministas casi duplican la tasa de éxito del agente.",
    "Las garantías en código dieron 0 incumplimientos de restricciones.",
    "Siguiente paso: atributos estructurados y un LLM más rápido."], 17, WHITE, space=6)
notes(s, 4, """(≈30 s) Cerramos con las limitaciones: el catálogo es estático y no tiene atributos estructurados; nuestras reglas son léxicas y tienen falsos positivos, como vimos en S11; la latencia no es de tiempo real; y la evaluación por voz usa turnos sintéticos y un solo hablante de referencia.

Como conclusión: construimos un asistente de compras completo por voz en español que corre íntegramente en Colab. El re-ranker mejora la búsqueda de forma significativa, las reglas deterministas casi duplican la tasa de éxito del agente y, sobre todo, poner las garantías en el código nos dio cero incumplimientos de restricciones. Como siguiente paso, añadiríamos atributos estructurados al catálogo y un LLM más rápido. Gracias.""")

# Guion literal (lo que dice cada persona) en las notas del orador
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from notas_guion import NOTES
assert len(NOTES) == len(prs.slides)
for i, sl in enumerate(prs.slides, 1):
    head, body = NOTES[i]
    sl.notes_slide.notes_text_frame.text = head + "\n\n" + body.strip()
prs.save(OUT)
print("ok", OUT, len(prs.slides), "diapositivas")
