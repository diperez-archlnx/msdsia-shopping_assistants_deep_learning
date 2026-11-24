"""Pruebas unitarias sin GPU ni descargas: python -m tests.test_unit (desde solucion/)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
tmp = Path(tempfile.mkdtemp())
os.environ["LAB4_BASE"] = str(tmp / "work")
os.environ["LAB4_STORE"] = str(tmp / "store")

import numpy as np
import pandas as pd

from lab4 import config as C
from lab4.textutils import spanish_numbers_to_digits, is_explicit_confirmation, tokenize, extract_amounts, extract_quantities
from lab4.state import detect_budget, ConversationState
from lab4.metrics import ndcg_at_k, wer, entity_errors, edit_distance
from lab4.retrieval import BM25Index, HybridSearcher, rrf, ranks_from_scores
from lab4.store import Store, StoreError
from lab4.tools import ShoppingTools
from lab4.llm import parse_output
from lab4.agent import tts_clean

ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1


# --- números y reglas -------------------------------------------------------
cases = {
    "quiero tres cuadernos y dos bolígrafos": "quiero 3 cuadernos y 2 bolígrafos",
    "treinta y dos euros": "32 euros",
    "un móvil": "un móvil",
    "talla media": "talla media",
    "media docena de huevos": "6 de huevos",
    "dos mil quinientos": "2500",
    "veinticinco euros": "25 euros",
    "uno y otro": "uno y otro",
}
for a, b in cases.items():
    got = spanish_numbers_to_digits(a)
    check(got == b, f"números: {a!r} -> {got!r} (esperado {b!r})")

for t, exp in [("Sí, confirmo el pedido.", True), ("Confirmo otra vez, por si acaso.", True),
               ("No, mejor cancela", False), ("Quiero comprar dos botellas", False),
               ("¿Y si compro también una taza?", False), ("Vale, cámbiala por la alternativa", False),
               ("De acuerdo, adelante", True)]:
    check(is_explicit_confirmation(t) == exp, f"confirmación {t!r}")

for t, exp in [("tengo un presupuesto de cuarenta euros", 40), ("con un máximo de treinta euros", 30),
               ("Mi presupuesto total es de veinticinco euros.", 25), ("hasta cuarenta euros", 40),
               ("Busca auriculares de menos de veinte euros.", None), ("hasta 3 mochilas", None),
               ("como mucho 1.000 euros", 1000), ("mi presupuesto es treinta euros", 30),
               ("máximo treinta euros en total", 30)]:
    check(detect_budget(t) == exp, f"presupuesto {t!r} -> {detect_budget(t)}")

check(extract_amounts("cuesta 12,50 euros y 3 €") == [12.5], f"importes {extract_amounts('cuesta 12,50 euros y 3 €')}")
check(extract_quantities("quiero 3 cuadernos de 2 euros") == [3.0], "cantidades")

# --- métricas ---------------------------------------------------------------
gains = {"a": 1.0, "b": 0.1, "c": 0.01, "d": 0.0}
check(abs(ndcg_at_k(["a", "b", "c", "d"], gains) - 1.0) < 1e-9, "nDCG ideal = 1")
check(ndcg_at_k(["d", "c", "b", "a"], gains) < 0.7, "nDCG invertido < 0.7")
check(ndcg_at_k(["x", "y"], gains) == 0.0, "nDCG sin relevantes = 0")
check(edit_distance(list("kitten"), list("sitting")) == 3, "levenshtein")
check(wer("quiero tres cuadernos", "quiero 3 cuadernos") == 0.0, "WER normaliza números")
e = entity_errors("quiero tres cuadernos por 20 euros", "quiero trece cuadernos por 20 euros", ["cuadernos"])
check(e["qty_err"] == 1 and e["amount_err"] == 0 and e["product_err"] == 0, f"entidades {e}")

# --- RRF y BM25 --------------------------------------------------------------
check(list(ranks_from_scores(np.array([0.1, 0.9, 0.5]))) == [3, 1, 2], "rangos")
titles = ["Botella de agua reutilizable acero", "Taza de café cerámica", "Cuaderno A5 de rayas",
          "Mochila para portátil impermeable", "Alfombrilla de ratón gaming", "Ratón inalámbrico USB"]
cat = pd.DataFrame({"product_id": [f"B0TEST{i:04d}" for i in range(len(titles))], "title": titles,
                    "description": ["apta para lavavajillas" if i == 0 else "" for i in range(len(titles))],
                    "bullets": ["" for _ in titles], "brand": ["Marca" for _ in titles],
                    "color": ["negro" for _ in titles]})
cat["passage"] = cat.title + ". " + cat.description
bm = BM25Index().fit(cat.title.tolist(), cat.passage.tolist())
s = bm.scores("botellas de agua")
check(int(np.argmax(s)) == 0, "BM25 encuentra la botella (stemming plural)")
check(bm.scores("raton inalambrico").argmax() == 5, "BM25 sin acentos")
cfg = C.RetrievalConfig(use_dense=False, use_reranker=False)
searcher = HybridSearcher(cat, bm, None, None, cfg)
hits = searcher.search("mochila portatil", k=3)
check(hits[0].product_id == "B0TEST0003", "búsqueda híbrida (solo BM25)")
check(searcher.rank_candidates("taza cafe", ["B0TEST0000", "B0TEST0001"])[0] == "B0TEST0001", "rank_candidates")

# --- tienda -------------------------------------------------------------------
st = Store(Path(os.environ["LAB4_STORE"]) / "t.db")
st.reset(cat.product_id.tolist(), seed=1)
inv1 = st.con.execute("SELECT * FROM inventory ORDER BY product_id").fetchall()
st.snapshot("base")
st.reset(cat.product_id.tolist(), seed=1)
check([tuple(r) for r in inv1] == [tuple(r) for r in st.con.execute("SELECT * FROM inventory ORDER BY product_id")],
      "reset determinista")
p0, p1 = cat.product_id[0], cat.product_id[1]
st.set_stock(p0, 5); st.set_stock(p1, 5); st.set_price(p0, 10); st.set_price(p1, 20)
st.set_cart_qty("u", p0, 2); st.set_cart_qty("u", p1, 1)
q = st.create_quote("u", budget_eur=100)
check(q["status"] == "open" and q["total_cents"] == 4000 + 499, f"cotización {q['total_cents']}")
st.set_stock(p1, 0)
try:
    st.confirm_order("u", q["quote_id"]); check(False, "debía fallar")
except StoreError as ex:
    check(ex.code == "stock_insuficiente", ex.code)
check(st.get(p0)["stock"] == 5 and not st.orders("u"), "sin cambios parciales")
st.set_stock(p1, 5)
q = st.create_quote("u", budget_eur=100)
r1 = st.confirm_order("u", q["quote_id"]); r2 = st.confirm_order("u", q["quote_id"])
check(r2["duplicate"] and len(st.orders("u")) == 1, "idempotencia")
check(st.get(p0)["stock"] == 3 and st.get(p1)["stock"] == 4 and st.cart("u") == [], "inventario y carrito")
st.restore("base")
check(not st.orders(), "restore")
st.set_stock(p0, 5); st.set_price(p0, 30)
st.set_cart_qty("v", p0, 2)
q = st.create_quote("v", budget_eur=50)
check(q["status"] == "invalid" and q["over_budget"], "cotización fuera de presupuesto")
st.restore("base")

# --- herramientas y memoria -----------------------------------------------------
state = ConversationState("s")
tools = ShoppingTools(st, searcher, cat, state)
r = tools.call("actualizar_carrito", {"producto": "1", "cantidad": 1})
check(r["error"] == "sin_resultados_previos", "referencia sin contexto")
r = tools.call("buscar_productos", {"consulta": "botella agua"})
check(r["ok"] and r["resultados"][0]["id"] == p0, "buscar")
st.set_stock(p0, 3)
check(tools.call("actualizar_carrito", {"producto": "1"})["error"] == "falta_cantidad", "falta cantidad")
check(tools.call("actualizar_carrito", {"producto": "1", "cantidad": 50})["error"] == "cantidad_fuera_de_rango", "rango")
check(tools.call("actualizar_carrito", {"producto": "1", "cantidad": 4})["error"] == "stock_insuficiente", "stock")
check(tools.call("actualizar_carrito", {"producto": "B0FAKE00000", "cantidad": 1})["error"] == "producto_no_mostrado", "id alucinado")
check(tools.call("buscar_productos", {"consulta": "x", "k": "cinco"})["ok"] is False, "argumento no numérico no rompe")
check(tools.call("verificar_atributo", {"producto": "1", "atributo": "lavavajillas"})["estado"] == "mencionado", "atributo mencionado")
check(tools.call("verificar_atributo", {"producto": "1", "atributo": "microondas"})["estado"] == "desconocido", "atributo desconocido")
check(tools.call("actualizar_carrito", {"producto": "1", "cantidad": 2})["ok"], "añadir")
state.turn = 1
q = tools.call("cotizar", {})
check(q["ok"] and state.pending_quote, "cotizar")
state.user_confirmed_this_turn = True
check(tools.call("confirmar_pedido", {})["error"] == "confirmacion_prematura", "no confirmar en el mismo turno")
state.turn = 2; state.user_confirmed_this_turn = False
check(tools.call("confirmar_pedido", {})["error"] == "sin_confirmacion_usuario", "exige confirmación")
state.user_confirmed_this_turn = True
r = tools.call("confirmar_pedido", {"cotizacion_id": q["cotizacion_id"]})
check(r["ok"] and not r["duplicate"], f"confirmar {r}")
r = tools.call("confirmar_pedido", {"cotizacion_id": q["cotizacion_id"]})
check(r["duplicate"] and len(st.orders("s")) == 1, "confirmación repetida")
check(len(state.ops) >= 10, "registro de operaciones")

# --- parser del LLM y TTS ------------------------------------------------------------
o = parse_output('Voy a buscar.<tool_call>\n{"name": "buscar_productos", "arguments": {"consulta": "taza", "k": 3}}\n</tool_call>')
check(o["tool_calls"][0]["arguments"]["k"] == 3 and o["text"] == "Voy a buscar.", "parser tool_call")
o = parse_output("<think>\n\n</think>\n\nHola, ¿qué necesitas?")
check(o["text"] == "Hola, ¿qué necesitas?" and not o["tool_calls"], "parser texto")
check(tts_clean("El **B0TEST0001** cuesta 12.99 €. Pedido P-1A2B3C4D.") ==
      "El cuesta doce con noventa y nueve euros. Pedido terminado en tres C cuatro D.",
      tts_clean("El **B0TEST0001** cuesta 12.99 €. Pedido P-1A2B3C4D."))

# --- texto para voz y regla de "el usuario ya eligió" ------------------------------------
from lab4.agent import quote_summary, CHOICE_RE
from lab4.textutils import number_to_words, short_title, spoken_numbers, normalize
for n, w in [(0, "cero"), (21, "veintiuno"), (30, "treinta"), (99, "noventa y nueve"), (100, "cien"),
             (101, "ciento uno"), (1250, "mil doscientos cincuenta"), (21000, "veintiún mil")]:
    check(number_to_words(n) == w, f"número en palabras {n} -> {number_to_words(n)!r}")
for t, exp in [("J.AKSO - Taza de café de cerámica con asa", "J.AKSO - Taza de café"),
               ("Cable USB Tipo C [3 Pack 1M] carga rápida", "Cable USB Tipo C"),
               ("Cuaderno A5 de rayas", "Cuaderno A5 de rayas")]:
    check(short_title(t) == exp, f"título corto {t!r} -> {short_title(t)!r}")
got = spoken_numbers("USB 2.0 y A5, 21 euros, 1 euro, 3,00 euros")
check(got == "USB 2.0 y A5, veintiún euros, un euro, tres euros", got)
qs = quote_summary({"lineas": [{"cantidad": 2, "titulo": "J.AKSO - Taza de café de cerámica", "precio_unit_eur": 7.99},
                               {"cantidad": 1, "titulo": "Cuaderno A5 de rayas", "precio_unit_eur": 3.0}],
                    "envio_eur": 4.99, "total_eur": 23.97}, budget=40)
check(tts_clean(qs) == "Te resumo la cotización: dos unidades de J.AKSO, Taza de café a siete con noventa y nueve "
      "euros; una unidad de Cuaderno A5 de rayas a tres euros; envío cuatro con noventa y nueve euros. Total: "
      "veintitrés con noventa y siete euros, dentro de tu presupuesto de cuarenta euros. ¿Confirmas el pedido?",
      tts_clean(qs))
for t, exp in [("Quiero dos tazas de café, la primera que encuentres está bien.", True),
               ("Me vale el primero que me muestres, prepara la cotización.", True),
               ("Vale, cámbiala por la alternativa que me propones y vuelve a cotizar.", True),
               ("Necesito un cargador.", False), ("Busca botellas de agua.", False), ("Sí, confirmo.", False)]:
    check(bool(CHOICE_RE.search(normalize(t))) == exp, f"elección ya hecha {t!r}")

print(f"✔ {ok} comprobaciones superadas")
