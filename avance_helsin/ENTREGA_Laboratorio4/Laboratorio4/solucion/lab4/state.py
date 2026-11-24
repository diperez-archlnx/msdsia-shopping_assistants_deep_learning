"""Estado de la conversación (memoria estructurada del agente).

El LLM no es la fuente de verdad: la memoria vive en este objeto y en la base de
datos de la tienda. En cada paso se le muestra al LLM un resumen JSON
(``to_prompt``) para que conserve presupuesto, cantidades y preferencias aunque
el historial textual se recorte.
"""
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from .textutils import normalize, spanish_numbers_to_digits


@dataclass
class ConversationState:
    session_id: str
    turn: int = 0
    budget_eur: Optional[float] = None
    preferences: dict = field(default_factory=dict)       # p. ej. {"color": "negro", "marca": "..."}
    last_results: list = field(default_factory=list)      # product_ids mostrados en la última búsqueda (orden = número)
    seen_products: list = field(default_factory=list)     # product_ids mostrados alguna vez (válidos para el carrito)
    pending_quote: Optional[dict] = None                  # última cotización válida pendiente de confirmar
    quote_turn: Optional[int] = None                      # turno en que se mostró la cotización
    orders: list = field(default_factory=list)
    user_confirmed_this_turn: bool = False
    history: list = field(default_factory=list)           # [(rol, texto)]
    ops: list = field(default_factory=list)               # registro de operaciones ejecutadas
    notes: list = field(default_factory=list)             # hechos detectados por reglas

    seen_titles: dict = field(default_factory=dict)       # id -> título corto (para que el LLM no confunda productos)

    def remember_results(self, pids, turn=None, titles=None):
        # Si en el mismo turno hubo varias búsquedas, un número ("1") sería ambiguo: se exige el id
        self.ambiguous_ordinals = turn is not None and getattr(self, "_results_turn", None) == turn
        self._results_turn = turn
        self.last_results = list(pids)
        for i, p in enumerate(pids):
            if p not in self.seen_products:
                self.seen_products.append(p)
            if titles is not None:
                self.seen_titles[p] = " ".join(str(titles[i]).split()[:7])

    def resolve_product(self, ref):
        """Acepta un product_id o una referencia ordinal ('2', 'segundo') a la última búsqueda."""
        if ref is None:
            return None, "falta_producto"
        r = normalize(str(ref)).strip()
        ordinals = {"primero": 1, "primera": 1, "segundo": 2, "segunda": 2, "tercero": 3, "tercera": 3,
                    "cuarto": 4, "cuarta": 4, "quinto": 5, "quinta": 5}
        n = None
        if r.isdigit() and len(r) <= 2:
            n = int(r)
        elif r in ordinals:
            n = ordinals[r]
        if n is not None:
            if not self.last_results:
                return None, "sin_resultados_previos"
            if getattr(self, "ambiguous_ordinals", False):
                return None, "referencia_ambigua"
            if not 1 <= n <= len(self.last_results):
                return None, "referencia_fuera_de_rango"
            return self.last_results[n - 1], None
        pid = str(ref).strip().upper()
        if pid in self.seen_products:
            return pid, None
        return None, "producto_no_mostrado"

    def to_prompt(self, cart_lines):
        def short(d):
            return {k: v for k, v in d.items() if v not in (None, [], {}, "")}
        return json.dumps(short({
            "turno": self.turn,
            "presupuesto_eur": self.budget_eur,
            "preferencias": self.preferences,
            "ultimos_resultados": [f"{i+1}: id {p} — {self.seen_titles.get(p, '')}" for i, p in enumerate(self.last_results)],
            "productos_mostrados_antes": [f"id {p} — {self.seen_titles.get(p, '')}" for p in self.seen_products[-12:]
                                          if p not in self.last_results],
            "carrito": cart_lines,
            "cotizacion_pendiente": self.pending_quote and {
                "cotizacion_id": self.pending_quote["quote_id"],
                "total_eur": self.pending_quote["total_eur"]},
            "usuario_confirmo_en_este_turno": self.user_confirmed_this_turn,
            "pedidos_registrados": self.orders,
            "hechos_detectados": self.notes[-5:],
        }), ensure_ascii=False)

    def to_dict(self):
        return asdict(self)


# "presupuesto (total) (es) (de) N": la unidad monetaria es opcional
_BUDGET_EXPLICIT_RE = re.compile(
    r"presupuesto(?: total)?(?: maximo)?(?: es)?(?: de)?\s*(\d+(?:[.,]\d+)?)", re.I)
# Resto de expresiones: exigen "euros"/"€" justo después del número ("hasta 3 mochilas" no es presupuesto).
# "menos de X euros" se excluye a propósito: suele ser un precio unitario máximo (filtro de búsqueda).
_BUDGET_RE = re.compile(
    r"(?:maximo(?: en total)?|como mucho|como maximo|no mas de|hasta|tope de|gastar)\s*(?:de\s*)?"
    r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?)\b", re.I)


_COLOR_RE = re.compile(
    r"\bcolor\s+(negr[oa]|azul|roj[oa]|blanc[oa]|verde|gris|rosa|amarill[oa]|morad[oa]|lila|naranja|marron|"
    r"beige|plata|platead[oa]|dorad[oa]|transparente|turquesa|granate)\b")


def detect_color(text):
    """Regla de respaldo: preferencia de color explícita ('de color azul')."""
    m = _COLOR_RE.search(normalize(text))
    return m.group(1) if m else None


def detect_budget(text):
    """Regla de respaldo: detecta un presupuesto explícito en el mensaje del usuario."""
    t = normalize(spanish_numbers_to_digits(text))
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", t)          # separador de miles: 1.000 -> 1000
    m = _BUDGET_EXPLICIT_RE.search(t) or _BUDGET_RE.search(t)
    if m:
        return float(m.group(1).replace(",", "."))
    return None
