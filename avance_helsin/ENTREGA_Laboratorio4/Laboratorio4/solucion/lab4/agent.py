"""Agente de compras: bucle ReAct con herramientas + guardas deterministas.

Por cada turno del usuario:
  1. Reglas de código actualizan la memoria (confirmación explícita, presupuesto).
  2. El LLM recibe: instrucciones, estado estructurado, historial reciente.
  3. Bucle de hasta ``max_steps`` pasos: el LLM elige herramientas; el código las valida
     y ejecuta; los resultados vuelven al LLM.
  4. Post-validación: la respuesta no puede afirmar un pedido que no existe, y se
     genera una versión apta para TTS (sin ids ni markdown).
"""
import json
import re
import time

from . import config as C
from .state import ConversationState, detect_budget, detect_color
from .textutils import is_explicit_confirmation, normalize, short_title, spoken_numbers
from .tools import ShoppingTools, TOOL_SCHEMAS

SYSTEM_PROMPT = """Eres "Clara", asistente de compras por voz de una tienda online española. Hablas siempre en español, de forma breve y natural, porque tus respuestas se leerán en voz alta.

REGLAS OBLIGATORIAS
1. Solo puedes recomendar productos devueltos por las herramientas. Apoya cada recomendación en su título o evidencia. Si un atributo no aparece en la ficha, di que es desconocido o que no lo puedes verificar; nunca lo inventes.
2. Precios y existencias: usa únicamente los datos de las herramientas. Indica si un producto está agotado.
3. Para añadir algo al carrito necesitas un producto concreto y una cantidad. Si falta información relevante (qué producto de la lista, cuántas unidades, un tipo/talla/compatibilidad que cambie la elección) o la petición es ambigua, haz UNA pregunta concreta y no modifiques el carrito.
   Pero si el usuario YA eligió ("el primero", "la primera que encuentres", "me quedo con la segunda", "elige los primeros") y dio la cantidad, actúa en el mismo turno sin pedir permiso: busca si hace falta y llama a actualizar_carrito para CADA producto pedido. Si pide la cotización, llama también a cotizar en el mismo turno.
   Si los resultados de búsqueda no son del tipo pedido o los más relevantes están agotados, dilo claramente.
4. Respeta siempre el presupuesto y las preferencias guardadas en el ESTADO. Cuando el usuario indique un presupuesto o una preferencia, guárdalo con registrar_restricciones. Si el usuario cambia una cantidad o preferencia, cambia solo eso y conserva lo demás.
5. Proceso de compra: actualizar_carrito -> cotizar -> leer al usuario productos, cantidades y total -> pedir confirmación explícita. Llama a confirmar_pedido SOLO si el usuario ha confirmado en este turno ("usuario_confirmo_en_este_turno": true) y hay una cotización pendiente.
6. Si una herramienta devuelve un error (agotado, stock_insuficiente, precio_modificado, presupuesto excedido...), explícalo y propone una solución: buscar_alternativa, menos unidades, u otro producto. Si no hay solución, dilo claramente. Tras cualquier cambio hay que volver a cotizar y pedir confirmación de nuevo.
7. Si el usuario repite una confirmación de un pedido ya registrado, no crees otro: informa de que ya está registrado.
8. Para referirte a productos ante el usuario usa un nombre corto; no leas identificadores. En las herramientas usa SIEMPRE el campo "id" del producto. Escribe los importes como "12,99 euros". Máximo 4 frases, sin tablas ni markdown.

EJEMPLO (el usuario ya eligió: actúa, no pidas permiso)
Usuario: Quiero dos toallas de baño y una sartén, las primeras que encuentres. Prepara la cotización.
Tú: buscar_productos({"consulta": "toalla de baño"}) -> resultado 1 con id "B0AAA11111"
Tú: buscar_productos({"consulta": "sartén"}) -> resultado 1 con id "B0BBB22222"
Tú: actualizar_carrito({"producto": "B0AAA11111", "cantidad": 2})
Tú: actualizar_carrito({"producto": "B0BBB22222", "cantidad": 1})
Tú: cotizar({})
Tú: (lees el resumen y pides confirmación)
"""


def tts_clean(text):
    """Texto apto para síntesis de voz: sin ids, markdown ni símbolos."""
    t = re.sub(r"\bB0[0-9A-Z]{8}\b", "", text)
    t = re.sub(r"\bP-[0-9A-F]{4}([0-9A-F]{4})\b", lambda m: "terminado en " + " ".join(m.group(1)), t)
    t = re.sub(r"\bQ-[0-9A-F]{8}\b", "", t)
    t = re.sub(r"[*_#`>|]+", " ", t)
    t = re.sub(r"(\d+)\.(\d{2})\b", r"\1,\2", t)
    t = t.replace("€", " euros").replace("%", " por ciento")
    # Lectura natural: "2 × Taza" -> "2 unidades de Taza"; fuera guiones sueltos y corchetes
    t = re.sub(r"(?<![\w.,])1\s*×\s*", "1 unidad de ", t)
    t = re.sub(r"(?<![\w.,])(\d+)\s*×\s*", r"\1 unidades de ", t)
    t = re.sub(r"\s[-–—]\s", ", ", t)
    t = re.sub(r"[\[\]{}]", " ", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = spoken_numbers(t)
    t = re.sub(r"\buno unidad\b", "una unidad", t)
    return re.sub(r"\s+([,.;:?!])", r"\1", t)


ORDER_CLAIM_RE = re.compile(r"(pedido|compra)\s+(ha sido|queda|qued[oó]|est[aá])\s+(registrad|confirmad|realizad)", re.I)
QUOTE_REQUEST_RE = re.compile(r"cotiz|resumen del pedido|cu[aá]nto (es|ser[ií]a) (el|en) total", re.I)
CART_TOOLS = {"actualizar_carrito", "vaciar_carrito", "reemplazar_en_carrito"}
ACTION_CLAIM_RE = re.compile(r"\b(a[ñn]ado|agrego|pongo|incluyo|he a[ñn]adido|he agregado)\b", re.I)
# El usuario ya eligió ("el primero que encuentres", "me quedo con la segunda", "la alternativa que propones")
CHOICE_RE = re.compile(r"\b(primer[oa]?s?|segund[oa]|tercer[oa]?|cuart[oa]|quint[oa]|la alternativa|"
                       r"el que (me )?(muestres|encuentres|propon\w+)|cualquiera)\b", re.I)


def _eur_txt(x):
    return (f"{int(x)}" if float(x).is_integer() else f"{x:.2f}".replace(".", ",")) + " euros"


def quote_summary(q, budget=None):
    """Resumen de cotización generado por CÓDIGO: los importes leídos al usuario son siempre exactos."""
    items = "; ".join(f"{l['cantidad']} × {short_title(l['titulo'])} a {_eur_txt(l['precio_unit_eur'])}"
                      for l in q["lineas"])
    envio = "envío gratis" if q["envio_eur"] == 0 else f"envío {_eur_txt(q['envio_eur'])}"
    txt = f"Te resumo la cotización: {items}; {envio}. Total: {_eur_txt(q['total_eur'])}"
    if budget is not None:
        txt += f", dentro de tu presupuesto de {_eur_txt(budget)}"
    return txt + ". ¿Confirmas el pedido?"


class ShoppingAgent:
    def __init__(self, llm, store, searcher, catalog, session_id="s1", cfg=C.AGENT, trace=False):
        self.llm, self.store, self.cfg, self.trace = llm, store, cfg, trace
        self.state = ConversationState(session_id=session_id)
        self.tools = ShoppingTools(store, searcher, catalog, self.state, cfg)

    # ------------------------------------------------------------------
    def _messages(self, turn_msgs):
        cart, _ = self.tools._cart_view()
        sys = SYSTEM_PROMPT + "\nESTADO ACTUAL (memoria fiable):\n" + self.state.to_prompt(cart)
        msgs = [{"role": "system", "content": sys}]
        # Historial textual recortado; el estado estructurado conserva lo importante
        hist = self.state.history[:-1][-2 * self.cfg.history_turns:]
        for role, text in hist:
            msgs.append({"role": role, "content": text})
        return msgs + turn_msgs

    def handle(self, user_text):
        st = self.state
        st.turn += 1
        timing = {"llm_s": 0.0, "tools_s": 0.0, "llm_calls": 0}
        t_start = time.perf_counter()
        st.history.append(("user", user_text))

        # 1) Reglas deterministas sobre el mensaje (desactivables para la ablación: cfg.use_rules=False,
        #    en cuyo caso el LLM decide solo y la guarda de confirmación queda abierta)
        rules = self.cfg.use_rules
        st.user_confirmed_this_turn = is_explicit_confirmation(user_text) if rules else True
        if rules:
            b = detect_budget(user_text)
            if b is not None and b != st.budget_eur:
                st.budget_eur = b
                st.notes.append(f"turno {st.turn}: presupuesto {b} euros detectado por regla")
            c = detect_color(user_text)
            if c and st.preferences.get("color") != c:
                st.preferences["color"] = c
                st.notes.append(f"turno {st.turn}: preferencia de color '{c}' detectada por regla")

        orders_before = len(st.orders)
        turn_msgs = [{"role": "user", "content": user_text}]
        final_text, steps, nudged = None, [], False
        for step in range(self.cfg.max_steps):
            out, stats = self.llm.generate(self._messages(turn_msgs), tools=TOOL_SCHEMAS)
            timing["llm_s"] += stats["gen_s"]; timing["llm_calls"] += 1
            if not out["tool_calls"]:
                # Autocorrección: la respuesta anuncia una acción sobre el carrito que no se ejecutó
                acted = any(s["tool"] in CART_TOOLS for s in steps)
                # Exceso de cautela: el usuario ya eligió entre productos mostrados y el LLM solo pregunta
                asks_permission = ("?" in (out["text"] or "") and st.last_results
                                   and CHOICE_RE.search(normalize(user_text)))
                if rules and not nudged and not acted and asks_permission:
                    nudged = True
                    st.notes.append(f"turno {st.turn}: el usuario ya había elegido; se pide al LLM que actúe")
                    turn_msgs += [{"role": "assistant", "content": out["text"]},
                                  {"role": "user", "content": "(sistema) El usuario ya eligió el producto en su "
                                   "mensaje: no pidas permiso. Si también indicó la cantidad, llama ahora a "
                                   "actualizar_carrito o reemplazar_en_carrito con el id y, si pidió cotización, a "
                                   "cotizar. Pregunta solo si de verdad falta la cantidad o el producto no es del "
                                   "tipo pedido."}]
                    continue
                if rules and not nudged and not acted and ACTION_CLAIM_RE.search(out["text"] or ""):
                    nudged = True
                    st.notes.append(f"turno {st.turn}: acción anunciada sin ejecutar; se pide al LLM que la ejecute")
                    turn_msgs += [{"role": "assistant", "content": out["text"]},
                                  {"role": "user", "content": "(sistema) Has dicho que modificas el carrito pero no "
                                   "has llamado a ninguna herramienta. Si el usuario ya eligió producto y cantidad, "
                                   "llama ahora a actualizar_carrito (con el id) para cada producto y, si pidió "
                                   "cotización, a cotizar. Si falta información, pregunta."}]
                    continue
                final_text = out["text"]
                break
            turn_msgs.append({"role": "assistant", "content": out["text"],
                              "tool_calls": [{"type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                                             for c in out["tool_calls"]]})
            for c in out["tool_calls"]:
                t0 = time.perf_counter()
                res = self.tools.call(c["name"], c["arguments"])
                timing["tools_s"] += time.perf_counter() - t0
                steps.append({"tool": c["name"], "args": c["arguments"], "result": res})
                if self.trace:
                    print(f"  ↳ {c['name']}({json.dumps(c['arguments'], ensure_ascii=False)}) -> "
                          f"{json.dumps(res, ensure_ascii=False)[:300]}")
                turn_msgs.append({"role": "tool", "name": c["name"],
                                  "content": json.dumps(res, ensure_ascii=False)})
        if final_text is None:
            # Límite de pasos: se fuerza una respuesta sin herramientas
            turn_msgs.append({"role": "user", "content": "(sistema) Responde ahora al usuario con lo que sabes."})
            out, stats = self.llm.generate(self._messages(turn_msgs), tools=None)
            timing["llm_s"] += stats["gen_s"]; timing["llm_calls"] += 1
            final_text = out["text"]

        # 3) Reglas de control deterministas: el flujo de compra no depende de que el LLM
        #    recuerde llamar a cotizar/confirmar, y los importes que se leen salen del código.
        if rules:
            final_text = self._control(user_text, steps, final_text, orders_before)

        # 4) Post-validación de la respuesta
        new_orders = st.orders[orders_before:]
        if ORDER_CLAIM_RE.search(final_text or "") and not new_orders and not any(
                s["tool"] == "confirmar_pedido" and s["result"].get("ok") for s in steps):
            final_text = ("Todavía no he registrado ningún pedido. "
                          + ("Hay una cotización pendiente: ¿confirmas la compra?" if st.pending_quote else
                             "¿Quieres que prepare la cotización?"))
            st.notes.append(f"turno {st.turn}: respuesta corregida (afirmaba un pedido inexistente)")
        for o in new_orders:
            if o["order_id"] not in (final_text or ""):
                final_text = (final_text or "") + f" Número de pedido: {o['order_id']}."
        final_text = final_text or "Perdona, ¿puedes repetirlo?"
        st.history.append(("assistant", final_text))
        timing["agent_total_s"] = time.perf_counter() - t_start
        return {"turn": st.turn, "user": user_text, "response": final_text, "tts_text": tts_clean(final_text),
                "steps": steps, "timing": timing}

    # ------------------------------------------------------------------
    def _control(self, user_text, steps, final_text, orders_before):
        st = self.state

        def run(name, args=None):
            res = self.tools.call(name, args or {})
            steps.append({"tool": name, "args": args or {}, "result": res, "por": "codigo"})
            return res

        llm_tools = {s["tool"] for s in steps}
        # a) Confirmación explícita de una cotización mostrada en un turno anterior
        if (st.user_confirmed_this_turn and st.pending_quote and st.quote_turn is not None
                and st.quote_turn < st.turn and "confirmar_pedido" not in llm_tools and not (llm_tools & CART_TOOLS)):
            r = run("confirmar_pedido", {"cotizacion_id": st.pending_quote["quote_id"]})
            if r.get("ok"):
                return f"¡Hecho! Pedido registrado con número {r['order_id']}, por un total de {_eur_txt(r['total'])}."
            return self._problem_text(r)
        if len(st.orders) > orders_before:
            return final_text
        # b) Cotización automática: carrito modificado, cotización pedida o confirmación solicitada sin cotizar
        quote = next((s["result"] for s in reversed(steps) if s["tool"] == "cotizar"), None)
        cart = self.store.cart(st.session_id)
        wants = (llm_tools & CART_TOOLS) or QUOTE_REQUEST_RE.search(user_text) or "confirm" in normalize(final_text or "")
        if quote is None and cart and st.pending_quote is None and wants:
            quote = run("cotizar")
            if not quote.get("ok"):
                return self._problem_text(quote)
        # c) Resumen de la cotización generado por código
        if quote is not None and quote.get("ok") and st.pending_quote:
            return quote_summary(quote, st.budget_eur)
        return final_text

    def _problem_text(self, r):
        """Explica en lenguaje natural por qué no se pudo cotizar o confirmar, con una propuesta."""
        titles = self.tools.cat["title"]
        name = lambda pid: " ".join(str(titles.get(pid, pid)).split()[:5])
        parts = []
        for p in r.get("stock_problems") or r.get("problemas_stock") or []:
            parts.append(f"de {name(p['product_id'])} solo quedan {p['disponible']} unidades y pediste {p['pedido']}")
        for p in r.get("price_changes") or []:
            parts.append(f"el precio de {name(p['product_id'])} cambió de {_eur_txt(p['antes'])} a {_eur_txt(p['ahora'])}")
        if r.get("excede_presupuesto") or r.get("error") == "presupuesto_excedido":
            tot = r.get("total_eur")
            parts.append(f"el total{' de ' + _eur_txt(tot) if tot else ''} supera tu presupuesto de "
                         f"{_eur_txt(self.state.budget_eur)}")
        if not parts:
            parts.append(r.get("message", "hubo un problema con el pedido"))
        return ("No he registrado el pedido: " + "; ".join(parts) +
                ". ¿Quieres que ajuste la cantidad o que busque una alternativa?")
