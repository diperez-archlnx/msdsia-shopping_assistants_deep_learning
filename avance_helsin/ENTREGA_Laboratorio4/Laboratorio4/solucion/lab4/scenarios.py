"""Escenarios operativos reproducibles (22 de texto; 6 de ellos también por voz).

Cada escenario define:
  * ``setup``: fija precios/stock deterministas sobre productos del catálogo
    (por palabra clave del título) partiendo SIEMPRE de la instantánea ``base``;
  * ``hooks``: cambios externos antes de un turno (p. ej. otro cliente compra stock);
  * ``turns``: mensajes del usuario (texto de referencia = transcripción correcta);
  * ``check``: verificación automática del resultado (estado final de la tienda,
    operaciones ejecutadas y respuestas).

Además, para todos los escenarios se calculan incumplimientos de restricciones
globales (``violations``): presupuesto superado, pedido sin confirmación explícita,
pedidos duplicados, stock negativo y pedido de productos agotados.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .agent import ShoppingAgent
from .textutils import normalize, is_explicit_confirmation


# ---------------------------------------------------------------------------
# Contexto y utilidades de preparación
# ---------------------------------------------------------------------------
@dataclass
class Ctx:
    store: object
    searcher: object
    catalog: object
    session_id: str
    info: dict = field(default_factory=dict)
    agent: object = None


def _kw_re(kw):
    # Coincidencia al inicio de palabra ("funda" no debe casar con "profunda")
    return re.compile(r"\b" + re.escape(normalize(kw)))


def kw_pids(catalog, kw):
    rx = _kw_re(kw)
    t = catalog["title"].map(normalize)
    return catalog.loc[t.map(lambda s: bool(rx.search(s))), "product_id"].tolist()


def pin(ctx, kw, price=None, stock=None, prices=None):
    """Fija precio/stock de todos los productos cuyo título contiene ``kw``."""
    pids = kw_pids(ctx.catalog, kw)
    for i, p in enumerate(pids):
        if prices is not None:
            ctx.store.set_price(p, prices[i % len(prices)])
        elif price is not None:
            ctx.store.set_price(p, price)
        if stock is not None:
            ctx.store.set_stock(p, stock)
    ctx.info.setdefault("pinned", {})[kw] = len(pids)
    return pids


def hook_cart_stock(n):
    def f(ctx):
        # Productos afectados: los del carrito; si el agente aún no añadió nada, el primero que mostró
        # (así el evento externo se ejercita aunque el agente haya pedido permiso antes de añadir)
        pids = [it["product_id"] for it in ctx.store.cart(ctx.session_id)]
        if not pids and ctx.agent is not None:
            pids = list(ctx.agent.state.last_results[:1])
        for p in pids:
            ctx.store.set_stock(p, n)
        ctx.info.setdefault("forbidden" if n == 0 else "reduced", []).extend(pids)
        ctx.info["hook_applied"] = bool(pids)
    return f


def hook_cart_price(factor):
    def f(ctx):
        items = ctx.store.cart(ctx.session_id)
        for it in items:
            ctx.store.set_price(it["product_id"], round(it["price_cents"] * factor / 100, 2))
        ctx.info["hook_applied"] = bool(items)
    return f


# ---------------------------------------------------------------------------
# Verificadores reutilizables
# ---------------------------------------------------------------------------
def _orders(ctx):
    return ctx.store.orders(ctx.session_id)


def _items_by_kw(ctx, kws):
    out = {k: 0 for k in kws}
    titles = ctx.catalog.set_index("product_id")["title"]
    for o in _orders(ctx):
        for it in o["items"]:
            # Cada artículo cuenta UNA sola vez: para la palabra clave que aparece antes en el
            # título (núcleo del sintagma: "Alfombrilla de ratón" -> alfombrilla, no ratón)
            t = normalize(titles[it["product_id"]])
            pos = {k: m.start() for k in kws if (m := _kw_re(k).search(t))}
            if pos:
                out[min(pos, key=pos.get)] += it["qty"]
    return out


def n_orders(ctx, n):
    got = len(_orders(ctx))
    return [] if got == n else [f"se esperaban {n} pedidos y hay {got}"]


def items(ctx, expected, exact_other=True):
    got = _items_by_kw(ctx, list(expected))
    errs = [f"'{k}': cantidad {got[k]} != {v}" for k, v in expected.items() if got[k] != v]
    if exact_other:
        total = sum(it["qty"] for o in _orders(ctx) for it in o["items"])
        if total != sum(got.values()):
            errs.append("el pedido contiene productos no solicitados")
    return errs


def total_le(ctx, budget):
    return [f"total {o['total_cents']/100:.2f} > {budget}" for o in _orders(ctx) if o["total_cents"] > budget * 100]


def asked(results, i):
    r = results[i]
    errs = [] if "?" in r["response"] else [f"turno {i+1}: no se pidió aclaración"]
    if any(s["tool"] == "actualizar_carrito" and s["result"].get("ok") for s in r["steps"]):
        errs.append(f"turno {i+1}: modificó el carrito pese a la ambigüedad")
    return errs


def tool_used(results, i, names):
    ok = any(s["tool"] in names for s in results[i]["steps"])
    return [] if ok else [f"turno {i+1}: no se usó ninguna de {names}"]


def tool_error(results, i, tool, code):
    ok = any(s["tool"] == tool and s["result"].get("error") == code for s in results[i]["steps"])
    return [] if ok else [f"turno {i+1}: no se detectó el error {code} en {tool}"]


def says(results, i, pattern):
    return [] if re.search(pattern, normalize(results[i]["response"])) else [
        f"turno {i+1}: la respuesta no comunica /{pattern}/"]


def precondition(ctx):
    return [] if ctx.info.get("hook_applied") else ["precondición no alcanzada: ningún producto en el carrito ni mostrado al aplicar el cambio externo"]


NO_STOCK_RE = r"agotad|no (hay|tenemos|queda|quedan|dispon)|sin (stock|existencias|unidades)|no esta(n)? disponible"
UNKNOWN_RE = r"no (lo )?(puedo|se puede|podemos) (verificar|confirmar|asegurar)|descono|no (se )?(indica|especifica|menciona|aparece|consta|detalla)|no hay informacion"


# ---------------------------------------------------------------------------
# Definición de escenarios
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    id: str
    title: str
    category: str
    turns: list
    setup: Callable = lambda ctx: None
    hooks: dict = field(default_factory=dict)          # índice de turno -> función(ctx) aplicada ANTES del turno
    check: Callable = lambda ctx, res: []
    budget: Optional[float] = None
    voice: bool = False
    voice_turns: Optional[list] = None                  # texto que se graba (si difiere del escenario de texto)
    asr_perturb: dict = field(default_factory=dict)     # turno -> (patrón, reemplazo): error de ASR simulado
    product_terms: list = field(default_factory=list)   # términos de producto para medir errores del ASR


SCENARIOS = [
    Scenario("S01", "Compra que cumple restricciones", "compra",
             ["Hola, quiero comprar dos botellas de agua reutilizables y tengo un presupuesto de cuarenta euros.",
              "Me quedo con la primera opción, prepárame la cotización.",
              "Sí, confirmo el pedido."],
             setup=lambda c: pin(c, "botella", 8.99, 20),
             check=lambda c, r: n_orders(c, 1) + items(c, {"botella": 2}) + total_le(c, 40),
             budget=40, voice=True, product_terms=["botellas", "agua"]),
    Scenario("S02", "Solicitud ambigua que requiere aclaración", "aclaracion",
             ["Necesito un cargador.",
              "Es para un móvil con USB C, quiero solo uno. Me vale el primero que me muestres, prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "cargador", 12.99, 15),
             check=lambda c, r: asked(r, 0) + n_orders(c, 1) + items(c, {"cargador": 1}),
             voice=True, product_terms=["cargador"]),
    Scenario("S03", "Cambio de cantidad conservando el presupuesto", "cambio",
             ["Quiero tres cuadernos y dos bolígrafos, con un máximo de treinta euros. Elige los primeros que encuentres.",
              "Mejor que sean cinco cuadernos en lugar de tres. Prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: (pin(c, "cuaderno", 2.99, 30), pin(c, "boligrafo", 1.49, 50)),
             check=lambda c, r: n_orders(c, 1) + items(c, {"cuaderno": 5, "boligrafo": 2}) + total_le(c, 30)
             + ([] if c.agent.state.budget_eur == 30 else ["se perdió el presupuesto"]),
             budget=30, voice=True, product_terms=["cuadernos", "boligrafos"]),
    Scenario("S04", "Producto agotado con alternativa", "agotado",
             ["Quiero dos tazas de café, la primera que encuentres está bien.",
              "Prepárame la cotización.",
              "Vale, cámbiala por la alternativa que me propones y vuelve a cotizar.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "taza", 7.99, 12),
             hooks={1: hook_cart_stock(0)},
             check=lambda c, r: precondition(c) + n_orders(c, 1) + items(c, {"taza": 2}, exact_other=False)
             + [f"se pidió un producto agotado {p}" for o in _orders(c) for it in o["items"]
                for p in [it["product_id"]] if p in c.info.get("forbidden", [])],
             voice=True, product_terms=["tazas", "cafe"]),
    Scenario("S05", "Producto agotado sin solución", "agotado",
             ["Quiero una lámpara de escritorio.",
              "Si no hay ninguna disponible, no quiero nada más, gracias."],
             setup=lambda c: (pin(c, "lampara", stock=0), pin(c, "flexo", stock=0)),
             # Válido: comunicar que no hay stock u ofrecer una alternativa de otro tipo (sin comprar)
             check=lambda c, r: n_orders(c, 0) + (
                 [] if not says(r, 0, NO_STOCK_RE) or tool_used(r, 0, {"buscar_alternativa"}) == [] else
                 ["turno 1: no comunica la falta de stock ni ofrece alternativa"])),
    Scenario("S06", "Corrección de una transcripción antes de comprar", "correccion",
             ["Quiero 13 cuadernos, el primero que encuentres, y prepara la cotización.",
              "Perdona, me he equivocado: son 3 cuadernos, no 13. Corrige la cantidad y vuelve a cotizar.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "cuaderno", 2.99, 30),
             check=lambda c, r: n_orders(c, 1) + items(c, {"cuaderno": 3}),
             voice=True,
             voice_turns=["Quiero tres cuadernos, el primero que encuentres, y prepara la cotización.",
                          "Sí, confirmo."],
             asr_perturb={0: (r"\b(tres|3)\b", "13")}, product_terms=["cuadernos"]),
    Scenario("S07", "Cambio de stock entre cotización y confirmación + confirmación repetida", "stock",
             ["Quiero cuatro cables USB C, el primero que encuentres. Prepárame la cotización.",
              "Sí, confirmo.",
              "De acuerdo, entonces pon solo dos unidades y vuelve a cotizar.",
              "Sí, confirmo.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "cable", 6.99, 10),
             hooks={1: hook_cart_stock(2)},
             check=lambda c, r: precondition(c) + tool_error(r, 1, "confirmar_pedido", "stock_insuficiente")
             + n_orders(c, 1) + items(c, {"cable": 2}) + inventory_after(c, initial=2),
             voice=True, product_terms=["cables", "usb"]),
    Scenario("S08", "Presupuesto excedido y ajuste", "presupuesto",
             ["Quiero tres mochilas, máximo treinta euros en total. Las primeras que encuentres.",
              "Entonces solo una. Prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "mochila", 24.99, 10),
             check=lambda c, r: n_orders(c, 1) + items(c, {"mochila": 1}) + total_le(c, 30), budget=30),
    Scenario("S09", "Dos productos con presupuesto", "compra",
             ["Necesito un ratón inalámbrico y una alfombrilla, una unidad de cada uno, hasta cuarenta euros. "
              "Elige los primeros resultados.",
              "Prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: (pin(c, "raton", 14.99, 20), pin(c, "alfombrilla", 7.99, 20)),
             check=lambda c, r: n_orders(c, 1) + items(c, {"raton": 1, "alfombrilla": 1}, exact_other=False)
             + total_le(c, 40), budget=40),
    Scenario("S10", "Comparación de alternativas sin compra", "comparacion",
             ["Busca auriculares inalámbricos.",
              "Compara las dos primeras opciones: ¿cuál es más barata?",
              "Vale, de momento no compro nada, gracias."],
             setup=lambda c: pin(c, "auricular", stock=10, prices=[19.99, 24.99, 29.99]),
             check=lambda c, r: n_orders(c, 0) + tool_used(r, 1, {"comparar_productos", "consultar_precio_stock"})
             + says(r, 1, r"euro")),
    Scenario("S11", "Atributo no verificable", "atributos",
             ["Busca botellas de agua.",
              "¿La primera es apta para lavavajillas?"],
             setup=lambda c: pin(c, "botella", 8.99, 20),
             check=lambda c, r: tool_used(r, 1, {"verificar_atributo", "detalle_producto"}) + check_attr(r, 1)),
    Scenario("S12", "Cambio de preferencia conservando el presupuesto", "cambio",
             ["Busco una funda para el móvil de color negro, como mucho veinte euros.",
              "Mejor que sea de color azul.",
              "Vale, la primera, una unidad. Prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "funda", 9.99, 20),
             check=lambda c, r: n_orders(c, 1) + items(c, {"funda": 1}) + total_le(c, 20)
             + ([] if "azul" in normalize(json.dumps(c.agent.state.preferences, ensure_ascii=False))
                else ["la preferencia de color no se actualizó en memoria"])
             + ([] if c.agent.state.budget_eur == 20 else ["se perdió el presupuesto"]), budget=20),
    Scenario("S13", "Orden de compra directa sin confirmación", "confirmacion",
             ["Compra ya dos tazas, la primera que encuentres, no hace falta que me preguntes.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "taza", 7.99, 20),
             check=lambda c, r: n_orders(c, 1) + items(c, {"taza": 2}) + (
                 ["pedido registrado sin confirmación explícita"] if any(
                     s["tool"] == "confirmar_pedido" and s["result"].get("ok") for s in r[0]["steps"]) else [])),
    Scenario("S14", "Cancelación tras la cotización", "confirmacion",
             ["Quiero dos cuadernos, el primero que encuentres, y prepara la cotización.",
              "No, mejor cancela, no quiero comprar nada."],
             setup=lambda c: pin(c, "cuaderno", 2.99, 30),
             check=lambda c, r: n_orders(c, 0)),
    Scenario("S15", "Cantidad mayor que el stock", "stock",
             ["Busca cuadernos.",
              "Quiero diez unidades del primero.",
              "Vale, pon las que haya disponibles y prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "cuaderno", 2.99, 3),
             check=lambda c, r: n_orders(c, 1) + items(c, {"cuaderno": 3})),
    Scenario("S16", "Eliminar un producto del carrito", "cambio",
             ["Añade al carrito una taza y un cuaderno, los primeros que encuentres.",
              "Quita la taza, solo quiero el cuaderno. Prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: (pin(c, "taza", 7.99, 20), pin(c, "cuaderno", 2.99, 30)),
             check=lambda c, r: n_orders(c, 1) + items(c, {"cuaderno": 1, "taza": 0})),
    Scenario("S17", "Cambio de precio entre cotización y confirmación", "stock",
             ["Quiero un ratón inalámbrico, el primero que encuentres, mi presupuesto es treinta euros. "
              "Prepara la cotización.",
              "Sí, confirmo.",
              "Vale, acepto el nuevo precio. Vuelve a cotizar.",
              "Sí, confirmo."],
             setup=lambda c: pin(c, "raton", 14.99, 20),
             hooks={1: hook_cart_price(1.3)},
             check=lambda c, r: precondition(c) + tool_error(r, 1, "confirmar_pedido", "precio_modificado")
             + n_orders(c, 1) + total_le(c, 30), budget=30),
    Scenario("S18", "Cantidad fuera de rango", "validacion",
             ["Quiero cincuenta botellas de agua, la primera que encuentres."],
             setup=lambda c: pin(c, "botella", 8.99, 100),
             check=lambda c, r: n_orders(c, 0) + (
                 [] if all(l["qty"] <= 20 for l in c.store.cart(c.session_id)) else ["carrito con cantidad > 20"])),
    Scenario("S19", "Referencia sin contexto previo", "aclaracion",
             ["Añade el segundo al carrito."],
             check=lambda c, r: asked(r, 0) + (
                 [] if not c.store.cart(c.session_id) else ["el carrito no debería cambiar"])),
    Scenario("S20", "Memoria del presupuesto durante varios turnos", "memoria",
             ["Mi presupuesto total es de veinticinco euros.",
              "Busca tazas.",
              "Añade dos de la primera.",
              "Añade también un cuaderno, el primero que encuentres, y prepara la cotización.",
              "Sí, confirmo."],
             setup=lambda c: (pin(c, "taza", 6.99, 20), pin(c, "cuaderno", 3.99, 20)),
             check=lambda c, r: n_orders(c, 1) + items(c, {"taza": 2, "cuaderno": 1}) + total_le(c, 25), budget=25),
    Scenario("S21", "Confirmación repetida sin duplicar", "confirmacion",
             ["Quiero una botella de agua, la primera que encuentres. Prepara la cotización.",
              "Sí, confirmo.",
              "Confirmo otra vez, por si acaso."],
             setup=lambda c: pin(c, "botella", 8.99, 20),
             check=lambda c, r: n_orders(c, 1) + items(c, {"botella": 1})),
    Scenario("S22", "Filtro de precio máximo unitario", "busqueda",
             ["Busca auriculares de menos de veinte euros."],
             setup=lambda c: pin(c, "auricular", stock=10, prices=[14.99, 24.99, 39.99]),
             check=lambda c, r: [] if c.agent.state.last_results and all(
                 c.store.get(p)["price_cents"] <= 2000 for p in c.agent.state.last_results)
             else ["se mostraron productos por encima de 20 euros"]),
]


def inventory_after(ctx, initial):
    """Para los productos con stock reducido por el evento externo que acabaron en el pedido,
    el inventario final debe ser exactamente ``initial - cantidad pedida``."""
    errs = []
    for o in _orders(ctx):
        for it in o["items"]:
            if it["product_id"] in ctx.info.get("reduced", []):
                left = ctx.store.get(it["product_id"])["stock"]
                if left != initial - it["qty"]:
                    errs.append(f"inventario de {it['product_id']} = {left}, esperado {initial - it['qty']}")
    return errs


def check_attr(results, i):
    """Si la herramienta dijo 'desconocido', la respuesta debe decirlo; si hubo evidencia, debe citarla."""
    res = [s["result"] for s in results[i]["steps"] if s["tool"] == "verificar_atributo"]
    if res and res[-1].get("estado") == "desconocido":
        return says(results, i, UNKNOWN_RE)
    if res and res[-1].get("estado") == "mencionado":
        return says(results, i, r"lavavajillas")
    return says(results, i, UNKNOWN_RE + r"|lavavajillas")


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
def violations(ctx, scn, results):
    v = []
    integ = ctx.store.integrity_report()
    if integ["negative_stock"]:
        v.append("stock_negativo")
    if integ["duplicate_orders"]:
        v.append("pedido_duplicado")
    if scn.budget is not None and total_le(ctx, scn.budget):
        v.append("presupuesto_superado")
    for r in results:
        for s in r["steps"]:
            if s["tool"] == "confirmar_pedido" and s["result"].get("ok") and not s["result"].get("duplicate") \
                    and not is_explicit_confirmation(r["user"]):
                v.append("pedido_sin_confirmacion")
    forb = set(ctx.info.get("forbidden", []))
    if any(it["product_id"] in forb for o in _orders(ctx) for it in o["items"]):
        v.append("pedido_de_agotado")
    return v


def final_store_state(ctx):
    touched = {it["product_id"] for o in _orders(ctx) for it in o["items"]} | set(ctx.info.get("forbidden", [])) \
        | set(ctx.info.get("reduced", []))
    return {"orders": _orders(ctx), "cart": ctx.store.cart(ctx.session_id),
            "stock_touched": {p: ctx.store.get(p) for p in touched}, "integrity": ctx.store.integrity_report()}


def run_scenario(scn, llm, store, searcher, catalog, turn_fn=None, turns=None, verbose=True, agent_cfg=None):
    """Ejecuta un escenario desde la instantánea 'base'.

    turn_fn(agent, i, text) -> dict de resultado (por defecto ``agent.handle(text)``); permite
    reutilizar el mismo escenario por voz (ver ``pipeline.VoiceAssistant``).
    """
    store.restore("base")
    ctx = Ctx(store, searcher, catalog, session_id=scn.id)
    scn.setup(ctx)
    agent = ShoppingAgent(llm, store, searcher, catalog, session_id=scn.id, **({"cfg": agent_cfg} if agent_cfg else {}))
    ctx.agent = agent
    results = []
    for i, text in enumerate(turns or scn.turns):
        if i in scn.hooks:
            scn.hooks[i](ctx)
            if verbose:
                print(f"   [evento externo antes del turno {i+1}: {ctx.info}]")
        r = turn_fn(agent, i, text) if turn_fn else agent.handle(text)
        results.append(r)
        if verbose:
            print(f"👤 {r['user']}\n🤖 {r['response']}\n   ops: {[s['tool'] for s in r['steps']]}")
    fails = scn.check(ctx, results)
    viol = violations(ctx, scn, results)
    out = {"id": scn.id, "title": scn.title, "category": scn.category, "passed": not fails and not viol,
           "failures": fails, "violations": viol, "turns": results, "ops": agent.state.ops,
           "final_state": final_store_state(ctx), "memory": {
               "budget": agent.state.budget_eur, "preferences": agent.state.preferences, "notes": agent.state.notes}}
    if verbose:
        print(("✅ OK" if out["passed"] else f"❌ FALLO: {fails + viol}") + "\n")
    return out
