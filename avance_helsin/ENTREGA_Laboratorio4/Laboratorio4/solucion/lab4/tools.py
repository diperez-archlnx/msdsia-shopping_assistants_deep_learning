"""Herramientas del agente.

Cada herramienta:
  * valida sus argumentos en código (tipos, rangos, existencia, stock, presupuesto);
  * devuelve un dict serializable con ``ok`` y datos o un código de error que el LLM
    debe explicar al usuario;
  * se registra en ``state.ops`` (operaciones ejecutadas, exigidas en el informe).

Las etiquetas ESCI no son accesibles desde aquí: solo se consulta el catálogo
(textos de producto) y la tienda simulada.
"""
import json
import time

from . import config as C
from .store import StoreError, eur
from .textutils import normalize, tokenize

UNKNOWN = "desconocido"


def _num(x, name, integer=False):
    if x is None or x == "":
        return None
    try:
        v = float(str(x).replace(",", ".").replace("€", "").strip())
    except ValueError:
        raise StoreError("argumento_invalido", f"'{name}' debe ser numérico (recibido: {x!r})")
    if integer:
        if not v.is_integer():
            raise StoreError("argumento_invalido", f"'{name}' debe ser un entero")
        v = int(v)
    return v


class ShoppingTools:
    def __init__(self, store, searcher, catalog, state, cfg=C.AGENT):
        self.store, self.searcher, self.state, self.cfg = store, searcher, state, cfg
        self.cat = catalog.set_index("product_id", drop=False)

    # ------------------------------------------------------------------ util
    def _card(self, pid, evidence=None):
        p = self.cat.loc[pid]
        inv = self.store.get(pid) or {}
        title = p["title"]
        return {
            "id": pid,
            "titulo": title[:120],
            "marca": p["brand"] or UNKNOWN,
            "color": p["color"] or UNKNOWN,
            "precio_eur": eur(inv["price_cents"]) if inv else UNKNOWN,
            "stock": inv.get("stock", UNKNOWN),
            "disponible": bool(inv) and inv["stock"] > 0,
            **({"evidencia": evidence} if evidence else {}),
        }

    def _cart_view(self):
        lines = self.store.cart(self.state.session_id)
        out = []
        for l in lines:
            out.append({"id": l["product_id"], "titulo": self.cat.loc[l["product_id"], "title"][:60],
                        "cantidad": l["qty"], "precio_unit_eur": eur(l["price_cents"]),
                        "stock": l["stock"]})
        totals = self.store.compute_totals(lines, self.cfg)
        return out, {k.replace("_cents", "_eur"): eur(v) for k, v in totals.items()}

    def _resolve(self, ref):
        pid, err = self.state.resolve_product(ref)
        if err:
            msgs = {"falta_producto": "No se indicó el producto",
                    "sin_resultados_previos": "Aún no se ha mostrado ninguna lista; busca primero",
                    "referencia_fuera_de_rango": "Ese número no existe en la última lista",
                    "producto_no_mostrado": "Ese id no se ha mostrado al usuario; usa buscar_productos",
                    "referencia_ambigua": "Hubo varias búsquedas en este turno: usa el campo id del producto, no su número"}
            raise StoreError(err, msgs[err])
        return pid

    # ------------------------------------------------------------- consultas
    def buscar_productos(self, consulta, precio_max=None, solo_disponibles=False, k=None):
        if not consulta or not str(consulta).strip():
            raise StoreError("argumento_invalido", "La consulta está vacía")
        k = int(k or self.cfg.search_k)
        k = max(1, min(k, 8))
        pmax = _num(precio_max, "precio_max")
        pids = self.searcher.cat["product_id"].values

        def allowed(i):
            if pmax is None and not solo_disponibles:
                return True
            inv = self.store.get(pids[i])
            if inv is None:
                return False
            if pmax is not None and inv["price_cents"] > pmax * 100:
                return False
            if solo_disponibles and inv["stock"] <= 0:
                return False
            return True

        hits = self.searcher.search(str(consulta), k=k, allowed=allowed)
        self.state.remember_results([h.product_id for h in hits], self.state.turn,
                                    [self.cat.at[h.product_id, "title"] for h in hits])
        res = [{"n": i + 1, **self._card(h.product_id, h.evidence)} for i, h in enumerate(hits)]
        out = {"ok": True, "consulta": consulta, "resultados": res,
               "nota": "Usa solo estos datos. Atributos ausentes = desconocido."}
        if solo_disponibles:
            # Transparencia: si el filtro ocultó los productos más relevantes por estar agotados, se informa
            top = self.searcher.search(str(consulta), k=k)
            agot = [h for h in top if (self.store.get(h.product_id) or {}).get("stock", 0) <= 0]
            if agot:
                out["agotados_mas_relevantes"] = len(agot)
                out["aviso"] = (f"{len(agot)} de los {len(top)} productos más relevantes para '{consulta}' están "
                                "agotados y no se muestran; díselo al usuario y comprueba que los resultados "
                                "son del tipo pedido.")
        return out

    def detalle_producto(self, producto):
        pid = self._resolve(producto)
        p = self.cat.loc[pid]
        return {"ok": True, **self._card(pid),
                "caracteristicas": (p["bullets"] or UNKNOWN)[:600],
                "descripcion": (p["description"] or UNKNOWN)[:500]}

    def verificar_atributo(self, producto, atributo, valor=None):
        """Comprueba un atributo SOLO con el texto del producto; si no aparece -> desconocido."""
        pid = self._resolve(producto)
        p = self.cat.loc[pid]
        a = normalize(atributo or "")
        field_map = {"color": "color", "marca": "brand"}
        if a in field_map and p[field_map[a]]:
            v = p[field_map[a]]
            match = None if valor is None else normalize(valor) in normalize(v)
            return {"ok": True, "atributo": atributo, "valor_en_ficha": v, "coincide": match, "fuente": a}
        text = " ".join([p["title"], p["bullets"], p["description"]])
        probe = tokenize(f"{atributo} {valor or ''}")
        sents = [s.strip() for s in text.replace(";", ".").split(".") if s.strip()]
        best, best_s = None, 0
        for s in sents:
            sc = len(set(probe) & set(tokenize(s)))
            if sc > best_s:
                best, best_s = s, sc
        need = max(1, len(set(probe)) // 2 + (1 if len(set(probe)) > 1 else 0))
        if best is None or best_s < need:
            return {"ok": True, "atributo": atributo, "estado": UNKNOWN,
                    "mensaje": "La ficha del producto no menciona este atributo; debe tratarse como desconocido."}
        return {"ok": True, "atributo": atributo, "estado": "mencionado", "evidencia": best[:250],
                "mensaje": "Responde citando la evidencia; no extrapoles."}

    def comparar_productos(self, productos):
        if not isinstance(productos, list) or len(productos) < 2:
            raise StoreError("argumento_invalido", "Indica al menos dos productos para comparar")
        cards = [self._card(self._resolve(x)) for x in productos[:4]]
        disponibles = [c for c in cards if c["disponible"] and c["precio_eur"] != UNKNOWN]
        cheapest = min(disponibles, key=lambda c: c["precio_eur"])["id"] if disponibles else None
        return {"ok": True, "productos": cards, "mas_barato_disponible": cheapest}

    def consultar_precio_stock(self, productos):
        if isinstance(productos, str):
            productos = [productos]
        return {"ok": True, "productos": [
            {k: v for k, v in self._card(self._resolve(x)).items() if k in ("id", "titulo", "precio_eur", "stock", "disponible")}
            for x in productos]}

    def buscar_alternativa(self, producto, cantidad=None, precio_max=None):
        """Productos similares (búsqueda por el título del original) con stock suficiente."""
        pid = self._resolve(producto)
        qty = _num(cantidad, "cantidad", integer=True) or 1
        pmax = _num(precio_max, "precio_max")
        title = self.cat.loc[pid, "title"]
        pids = self.searcher.cat["product_id"].values

        def allowed(i):
            if pids[i] == pid:
                return False
            inv = self.store.get(pids[i])
            return bool(inv) and inv["stock"] >= qty and (pmax is None or inv["price_cents"] <= pmax * 100)

        hits = self.searcher.search(title, k=3, allowed=allowed)
        self.state.remember_results([h.product_id for h in hits], self.state.turn,
                                    [self.cat.at[h.product_id, "title"] for h in hits])
        if not hits:
            return {"ok": True, "resultados": [], "mensaje": "No hay alternativas con stock suficiente"}
        return {"ok": True, "original": pid,
                "resultados": [{"n": i + 1, **self._card(h.product_id, h.evidence)} for i, h in enumerate(hits)]}

    # ---------------------------------------------------------------- memoria
    def registrar_restricciones(self, presupuesto=None, preferencias=None):
        b = _num(presupuesto, "presupuesto")
        if b is not None:
            if b <= 0:
                raise StoreError("argumento_invalido", "El presupuesto debe ser positivo")
            self.state.budget_eur = b
        if isinstance(preferencias, str):
            try:
                preferencias = json.loads(preferencias)
            except ValueError:
                preferencias = {"otros": preferencias}
        if isinstance(preferencias, dict):
            for k, v in preferencias.items():
                if v in (None, "", "ninguna"):
                    self.state.preferences.pop(k, None)
                else:
                    self.state.preferences[k] = v
        return {"ok": True, "presupuesto_eur": self.state.budget_eur, "preferencias": self.state.preferences}

    # ---------------------------------------------------------------- carrito
    def actualizar_carrito(self, producto, cantidad=None):
        """Fija la cantidad de un producto en el carrito (0 = quitar)."""
        pid = self._resolve(producto)
        if cantidad is None or cantidad == "":
            raise StoreError("falta_cantidad", "Falta la cantidad: pregunta al usuario cuántas unidades quiere")
        qty = _num(cantidad, "cantidad", integer=True)
        if qty < 0 or qty > self.cfg.max_qty_per_item:
            raise StoreError("cantidad_fuera_de_rango",
                             f"La cantidad debe estar entre 0 y {self.cfg.max_qty_per_item}")
        inv = self.store.get(pid)
        if qty > 0 and inv["stock"] == 0:
            raise StoreError("agotado", "Producto agotado; usa buscar_alternativa", {"producto": pid})
        if qty > inv["stock"]:
            raise StoreError("stock_insuficiente", f"Solo hay {inv['stock']} unidades",
                             {"producto": pid, "disponible": inv["stock"], "pedido": qty})
        self.store.set_cart_qty(self.state.session_id, pid, qty)
        self._invalidate_quote()
        lines, totals = self._cart_view()
        res = {"ok": True, "carrito": lines, **totals}
        if self.state.budget_eur is not None and totals["total_eur"] > self.state.budget_eur:
            res["aviso"] = (f"El total ({totals['total_eur']} €) supera el presupuesto de "
                            f"{self.state.budget_eur} €")
        return res

    def reemplazar_en_carrito(self, producto_actual, producto_nuevo, cantidad=None):
        """Sustituye un producto del carrito por otro (p. ej. la alternativa a uno agotado).

        Conserva la cantidad si no se indica otra; si el nuevo no tiene stock suficiente, el
        carrito no se modifica.
        """
        old = self._resolve(producto_actual)
        new = self._resolve(producto_nuevo)
        lines = {l["product_id"]: l["qty"] for l in self.store.cart(self.state.session_id)}
        if old not in lines:
            raise StoreError("no_en_carrito", "El producto actual no está en el carrito")
        qty = _num(cantidad, "cantidad", integer=True) or lines[old]
        inv = self.store.get(new)
        if inv["stock"] < qty:
            raise StoreError("stock_insuficiente", f"Solo hay {inv['stock']} unidades del nuevo producto",
                             {"producto": new, "disponible": inv["stock"], "pedido": qty})
        self.store.set_cart_qty(self.state.session_id, old, 0)
        self.store.set_cart_qty(self.state.session_id, new, qty)
        self._invalidate_quote()
        cart, totals = self._cart_view()
        return {"ok": True, "carrito": cart, **totals}

    def ver_carrito(self):
        lines, totals = self._cart_view()
        return {"ok": True, "carrito": lines, **totals, "presupuesto_eur": self.state.budget_eur}

    def vaciar_carrito(self):
        self.store.clear_cart(self.state.session_id)
        self._invalidate_quote()
        return {"ok": True, "carrito": []}

    def _invalidate_quote(self):
        self.state.pending_quote = None
        self.state.quote_turn = None

    # -------------------------------------------------------------- cotización
    def cotizar(self):
        q = self.store.create_quote(self.state.session_id, self.state.budget_eur)
        lines = [{"titulo": self.cat.loc[l["product_id"], "title"][:60], "id": l["product_id"],
                  "cantidad": l["qty"], "precio_unit_eur": eur(l["unit_price_cents"]),
                  "importe_eur": eur(l["qty"] * l["unit_price_cents"])} for l in q["lines"]]
        res = {"ok": q["status"] == "open", "cotizacion_id": q["quote_id"], "lineas": lines,
               "subtotal_eur": eur(q["subtotal_cents"]), "envio_eur": eur(q["shipping_cents"]),
               "total_eur": eur(q["total_cents"]), "presupuesto_eur": self.state.budget_eur}
        if q["stock_problems"]:
            res["problemas_stock"] = q["stock_problems"]
        if q["over_budget"]:
            res["excede_presupuesto"] = True
        if res["ok"]:
            self.state.pending_quote = {"quote_id": q["quote_id"], "total_eur": res["total_eur"]}
            self.state.quote_turn = self.state.turn
            res["siguiente_paso"] = "Lee el resumen al usuario y pide confirmación explícita. NO confirmes todavía."
        else:
            self._invalidate_quote()
            res["siguiente_paso"] = "Explica el problema y propone una solución (alternativa, menos unidades)."
        return res

    def confirmar_pedido(self, cotizacion_id=None):
        st = self.state
        # Repetición de una confirmación ya procesada => la tienda devuelve el pedido existente
        if cotizacion_id and any(o["quote_id"] == cotizacion_id for o in st.orders):
            return self.store.confirm_order(st.session_id, cotizacion_id, st.budget_eur)
        if st.pending_quote is None:
            if st.orders:
                last = st.orders[-1]
                return {"ok": True, "duplicate": True, "order_id": last["order_id"],
                        "message": "No hay cotización pendiente; el último pedido ya está registrado y no se duplica."}
            raise StoreError("sin_cotizacion", "No hay cotización vigente: llama a cotizar primero")
        # Guardas de proceso: la confirmación debe venir del usuario DESPUÉS de ver la cotización
        if not st.user_confirmed_this_turn:
            raise StoreError("sin_confirmacion_usuario",
                             "El usuario no ha confirmado explícitamente en este turno; pídele confirmación")
        if st.quote_turn is not None and st.quote_turn >= st.turn:
            raise StoreError("confirmacion_prematura",
                             "La cotización se acaba de generar; muéstrala y espera la confirmación del usuario")
        qid = st.pending_quote["quote_id"]
        if cotizacion_id and cotizacion_id != qid:
            raise StoreError("cotizacion_distinta", f"La cotización vigente es {qid}")
        try:
            r = self.store.confirm_order(st.session_id, qid, st.budget_eur)
        except StoreError:
            self._invalidate_quote()          # la cotización queda obsoleta: hay que recotizar
            raise
        if not r.get("duplicate"):
            st.orders.append({"order_id": r["order_id"], "quote_id": qid, "total_eur": r["total"]})
        self._invalidate_quote()
        return r

    # ------------------------------------------------------------- despacho
    def call(self, name, args):
        fn = getattr(self, name, None)
        if fn is None or name.startswith("_") or name not in TOOL_NAMES:
            return {"ok": False, "error": "herramienta_desconocida", "message": name}
        t0 = time.perf_counter()
        try:
            res = fn(**(args or {}))
        except StoreError as e:
            res = e.to_dict()
        except (TypeError, ValueError) as e:
            res = {"ok": False, "error": "argumentos_invalidos", "message": str(e)}
        except Exception as e:                # un error de herramienta nunca debe tumbar la conversación
            res = {"ok": False, "error": "error_interno", "message": f"{type(e).__name__}: {e}"}
        self.state.ops.append({"turn": self.state.turn, "tool": name, "args": args,
                               "ok": res.get("ok", False), "error": res.get("error"),
                               "ms": round(1000 * (time.perf_counter() - t0), 1)})
        return res


def _fn(name, desc, props, required=()):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": list(required)}}}


PRODUCT_REF = {"type": "string", "description": "id del producto (campo id de los resultados)"}

TOOL_SCHEMAS = [
    _fn("buscar_productos", "Busca productos en el catálogo (RAG híbrido). Devuelve título, precio, stock y evidencia textual.",
        {"consulta": {"type": "string", "description": "descripción del producto en español"},
         "precio_max": {"type": "number", "description": "precio unitario máximo en euros"},
         "solo_disponibles": {"type": "boolean", "description": "excluir agotados"},
         "k": {"type": "integer", "description": "número de resultados (1-8)"}}, ["consulta"]),
    _fn("detalle_producto", "Ficha completa de un producto ya mostrado.", {"producto": PRODUCT_REF}, ["producto"]),
    _fn("verificar_atributo", "Comprueba si la ficha menciona un atributo (material, tamaño, compatibilidad...). Si no aparece, es desconocido.",
        {"producto": PRODUCT_REF, "atributo": {"type": "string"}, "valor": {"type": "string"}}, ["producto", "atributo"]),
    _fn("comparar_productos", "Compara precio, stock, marca y color de 2 a 4 productos.",
        {"productos": {"type": "array", "items": {"type": "string"}}}, ["productos"]),
    _fn("consultar_precio_stock", "Precio y existencias actuales.",
        {"productos": {"type": "array", "items": {"type": "string"}}}, ["productos"]),
    _fn("buscar_alternativa", "Busca productos similares con stock suficiente cuando uno está agotado o no alcanza.",
        {"producto": PRODUCT_REF, "cantidad": {"type": "integer"}, "precio_max": {"type": "number"}}, ["producto"]),
    _fn("registrar_restricciones", "Guarda en memoria el presupuesto total y/o preferencias del usuario.",
        {"presupuesto": {"type": "number", "description": "presupuesto total en euros"},
         "preferencias": {"type": "object", "description": "p. ej. {\"color\": \"negro\"}"}}),
    _fn("actualizar_carrito", "Fija la cantidad de un producto en el carrito (0 lo elimina).",
        {"producto": PRODUCT_REF, "cantidad": {"type": "integer"}}, ["producto", "cantidad"]),
    _fn("reemplazar_en_carrito", "Sustituye en el carrito un producto por otro (p. ej. por la alternativa a uno agotado), "
        "conservando la cantidad salvo que se indique otra.",
        {"producto_actual": PRODUCT_REF, "producto_nuevo": PRODUCT_REF, "cantidad": {"type": "integer"}},
        ["producto_actual", "producto_nuevo"]),
    _fn("ver_carrito", "Muestra el carrito y los totales.", {}),
    _fn("vaciar_carrito", "Elimina todos los productos del carrito.", {}),
    _fn("cotizar", "Genera la cotización del carrito (valida stock y presupuesto).", {}),
    _fn("confirmar_pedido", "Registra el pedido de la cotización vigente. Solo tras confirmación explícita del usuario.",
        {"cotizacion_id": {"type": "string"}}),
]
TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}
