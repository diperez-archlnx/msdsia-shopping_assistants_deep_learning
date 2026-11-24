"""Tienda simulada sobre SQLite.

* Precios y existencias se generan con semilla fija (``reset``) => reproducible y restaurable.
* ``snapshot``/``restore`` copian el fichero de base de datos para fijar estados iniciales
  de cada escenario.
* ``confirm_order`` ejecuta, dentro de UNA transacción ``BEGIN IMMEDIATE``:
    1. idempotencia: si ya existe un pedido para esa cotización, lo devuelve (no duplica);
    2. re-validación de stock, precio y presupuesto contra el estado ACTUAL;
    3. descuento de inventario + inserción del pedido + vaciado del carrito.
  Cualquier fallo provoca ROLLBACK: no hay cambios parciales.
* Todas las cantidades monetarias se guardan en céntimos (enteros) para evitar
  errores de coma flotante en presupuestos.
"""
import hashlib
import json
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

import numpy as np

from . import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    stock INTEGER NOT NULL CHECK (stock >= 0),
    version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS carts (
    session_id TEXT NOT NULL,
    product_id TEXT NOT NULL REFERENCES inventory(product_id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    PRIMARY KEY (session_id, product_id)
);
CREATE TABLE IF NOT EXISTS quotes (
    quote_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    quote_id TEXT NOT NULL UNIQUE,          -- clave de idempotencia
    created_at REAL NOT NULL,
    total_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    ts REAL, session_id TEXT, kind TEXT, detail TEXT
);
"""


class StoreError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data or {}

    def to_dict(self):
        return {"ok": False, "error": self.code, "message": self.message, **self.data}


def eur(cents):
    return round(cents / 100.0, 2)


class Store:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path or C.STORE_DIR / "store.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self):
        # isolation_level=None => control manual de transacciones (BEGIN/COMMIT explícitos)
        self.con = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)

    # ------------------------------------------------------------------ estado
    def reset(self, product_ids, seed=C.SEED, out_of_stock_rate=0.08):
        """Regenera la tienda de forma determinista a partir de la semilla.

        El precio depende de una semilla derivada de (seed, product_id), de modo
        que un producto tiene siempre el mismo precio aunque cambie el orden del catálogo.
        """
        rows = []
        for i, pid in enumerate(product_ids):
            h = int(hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest()[:12], 16)
            rng = np.random.default_rng(h)
            price = float(np.clip(rng.lognormal(mean=3.1, sigma=0.8), 3.0, 600.0))  # mediana ~22 €
            price = np.floor(price) + 0.99 if price > 10 else round(price, 2)
            stock = 0 if rng.random() < out_of_stock_rate else int(rng.integers(1, 40))
            rows.append((pid, int(round(price * 100)), stock))
        self.con.execute("BEGIN")
        try:
            for t in ["order_items", "orders", "quotes", "carts", "events", "inventory"]:
                self.con.execute(f"DELETE FROM {t}")
            self.con.executemany("INSERT INTO inventory(product_id, price_cents, stock) VALUES (?,?,?)", rows)
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        return len(rows)

    def snapshot(self, name):
        dst = self.db_path.parent / f"snapshot_{name}.db"
        bk = sqlite3.connect(dst)
        self.con.backup(bk)
        bk.close()
        return dst

    def restore(self, name):
        src = self.db_path.parent / f"snapshot_{name}.db"
        if not src.exists():
            raise FileNotFoundError(src)
        sc = sqlite3.connect(src)
        sc.backup(self.con)
        sc.close()

    def log(self, session_id, kind, detail):
        self.con.execute("INSERT INTO events VALUES (?,?,?,?)",
                         (time.time(), session_id, kind, json.dumps(detail, ensure_ascii=False)))

    # ------------------------------------------------------------- consultas
    def get(self, product_id):
        r = self.con.execute("SELECT * FROM inventory WHERE product_id=?", (product_id,)).fetchone()
        return dict(r) if r else None

    def get_many(self, product_ids):
        if not product_ids:
            return {}
        q = ",".join("?" * len(product_ids))
        rows = self.con.execute(f"SELECT * FROM inventory WHERE product_id IN ({q})", list(product_ids))
        return {r["product_id"]: dict(r) for r in rows}

    def set_stock(self, product_id, stock, session_id="admin"):
        """Modificación externa (otro cliente / almacén). Usada en escenarios."""
        self.con.execute("UPDATE inventory SET stock=?, version=version+1 WHERE product_id=?", (stock, product_id))
        self.log(session_id, "set_stock", {"product_id": product_id, "stock": stock})

    def set_price(self, product_id, price_eur, session_id="admin"):
        self.con.execute("UPDATE inventory SET price_cents=?, version=version+1 WHERE product_id=?",
                         (int(round(price_eur * 100)), product_id))
        self.log(session_id, "set_price", {"product_id": product_id, "price": price_eur})

    # ---------------------------------------------------------------- carrito
    def cart(self, session_id):
        rows = self.con.execute(
            "SELECT c.product_id, c.qty, i.price_cents, i.stock FROM carts c "
            "JOIN inventory i USING(product_id) WHERE c.session_id=? ORDER BY c.rowid", (session_id,))
        return [dict(r) for r in rows]

    def set_cart_qty(self, session_id, product_id, qty):
        if self.get(product_id) is None:
            raise StoreError("producto_inexistente", f"El producto {product_id} no existe en la tienda")
        if qty <= 0:
            self.con.execute("DELETE FROM carts WHERE session_id=? AND product_id=?", (session_id, product_id))
        else:
            self.con.execute(
                "INSERT INTO carts(session_id, product_id, qty) VALUES (?,?,?) "
                "ON CONFLICT(session_id, product_id) DO UPDATE SET qty=excluded.qty",
                (session_id, product_id, int(qty)))
        self.log(session_id, "cart_set", {"product_id": product_id, "qty": qty})

    def clear_cart(self, session_id):
        self.con.execute("DELETE FROM carts WHERE session_id=?", (session_id,))

    # -------------------------------------------------------------- cotización
    def compute_totals(self, lines, cfg=C.AGENT):
        subtotal = sum(l["qty"] * l["price_cents"] for l in lines)
        shipping = 0 if subtotal == 0 or subtotal >= cfg.free_shipping_from * 100 else int(round(cfg.shipping_flat * 100))
        # Los precios del catálogo incluyen IVA; se desglosa a título informativo
        vat = int(round(subtotal - subtotal / (1 + cfg.tax_rate)))
        return {"subtotal_cents": subtotal, "shipping_cents": shipping, "vat_included_cents": vat,
                "total_cents": subtotal + shipping}

    def create_quote(self, session_id, budget_eur=None):
        lines = self.cart(session_id)
        if not lines:
            raise StoreError("carrito_vacio", "El carrito está vacío")
        problems = []
        for l in lines:
            if l["stock"] < l["qty"]:
                problems.append({"product_id": l["product_id"], "pedido": l["qty"], "disponible": l["stock"]})
        totals = self.compute_totals(lines)
        over_budget = budget_eur is not None and totals["total_cents"] > int(round(budget_eur * 100))
        quote_id = "Q-" + uuid.uuid4().hex[:8].upper()
        payload = {"lines": [{"product_id": l["product_id"], "qty": l["qty"], "unit_price_cents": l["price_cents"]}
                             for l in lines],
                   "budget_cents": None if budget_eur is None else int(round(budget_eur * 100)), **totals}
        status = "open" if not problems and not over_budget else "invalid"
        self.con.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?)",
                         (quote_id, session_id, time.time(), json.dumps(payload), totals["total_cents"], status))
        self.log(session_id, "quote", {"quote_id": quote_id, "status": status})
        return {"quote_id": quote_id, "status": status, "stock_problems": problems,
                "over_budget": over_budget, **payload}

    # ----------------------------------------------------------------- pedido
    def confirm_order(self, session_id, quote_id, budget_eur=None):
        """Confirma un pedido de forma atómica e idempotente."""
        cur = self.con.cursor()
        cur.execute("BEGIN IMMEDIATE")          # bloquea escritores concurrentes
        try:
            dup = cur.execute("SELECT order_id, total_cents FROM orders WHERE quote_id=?", (quote_id,)).fetchone()
            if dup:
                cur.execute("COMMIT")
                return {"ok": True, "duplicate": True, "order_id": dup["order_id"], "total": eur(dup["total_cents"]),
                        "message": "Este pedido ya estaba registrado; no se ha creado otro."}
            q = cur.execute("SELECT * FROM quotes WHERE quote_id=? AND session_id=?", (quote_id, session_id)).fetchone()
            if q is None:
                raise StoreError("cotizacion_inexistente", "No existe esa cotización")
            if q["status"] != "open":
                raise StoreError("cotizacion_no_valida", f"La cotización está en estado '{q['status']}'")
            payload = json.loads(q["payload"])
            # El carrito actual debe coincidir con lo cotizado (si el usuario cambió algo, hay que recotizar)
            cart_now = {l["product_id"]: l["qty"] for l in self.cart(session_id)}
            quoted = {l["product_id"]: l["qty"] for l in payload["lines"]}
            if cart_now != quoted:
                raise StoreError("carrito_modificado", "El carrito cambió después de la cotización; hay que recotizar")
            inv = self.get_many(list(quoted))
            stock_problems, price_changes = [], []
            for l in payload["lines"]:
                it = inv[l["product_id"]]
                if it["stock"] < l["qty"]:
                    stock_problems.append({"product_id": l["product_id"], "pedido": l["qty"], "disponible": it["stock"]})
                if it["price_cents"] != l["unit_price_cents"]:
                    price_changes.append({"product_id": l["product_id"], "antes": eur(l["unit_price_cents"]),
                                          "ahora": eur(it["price_cents"])})
            if stock_problems:
                raise StoreError("stock_insuficiente", "El stock cambió desde la cotización",
                                 {"stock_problems": stock_problems})
            if price_changes:
                raise StoreError("precio_modificado", "El precio cambió desde la cotización",
                                 {"price_changes": price_changes})
            budget_cents = int(round(budget_eur * 100)) if budget_eur is not None else payload.get("budget_cents")
            if budget_cents is not None and payload["total_cents"] > budget_cents:
                raise StoreError("presupuesto_excedido", "El total supera el presupuesto")
            order_id = "P-" + uuid.uuid4().hex[:8].upper()
            cur.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                        (order_id, session_id, quote_id, time.time(), payload["total_cents"]))
            for l in payload["lines"]:
                # El CHECK (stock >= 0) y la condición del WHERE son una segunda barrera
                r = cur.execute("UPDATE inventory SET stock = stock - ?, version = version + 1 "
                                "WHERE product_id=? AND stock >= ?", (l["qty"], l["product_id"], l["qty"]))
                if r.rowcount != 1:
                    raise StoreError("stock_insuficiente", "Stock insuficiente al descontar inventario")
                cur.execute("INSERT INTO order_items VALUES (?,?,?,?)",
                            (order_id, l["product_id"], l["qty"], l["unit_price_cents"]))
            cur.execute("UPDATE quotes SET status='confirmed' WHERE quote_id=?", (quote_id,))
            cur.execute("DELETE FROM carts WHERE session_id=?", (session_id,))
            cur.execute("INSERT INTO events VALUES (?,?,?,?)",
                        (time.time(), session_id, "order", json.dumps({"order_id": order_id, "quote_id": quote_id})))
            cur.execute("COMMIT")
            return {"ok": True, "duplicate": False, "order_id": order_id, "total": eur(payload["total_cents"]),
                    "lines": payload["lines"]}
        except StoreError as e:
            cur.execute("ROLLBACK")
            if e.code in ("stock_insuficiente", "precio_modificado", "carrito_modificado", "presupuesto_excedido"):
                self.con.execute("UPDATE quotes SET status='stale' WHERE quote_id=? AND status='open'", (quote_id,))
            raise
        except Exception:
            cur.execute("ROLLBACK")
            raise

    def orders(self, session_id=None):
        sql = "SELECT * FROM orders" + (" WHERE session_id=?" if session_id else "") + " ORDER BY created_at"
        rows = self.con.execute(sql, (session_id,) if session_id else ())
        out = []
        for o in rows:
            o = dict(o)
            o["items"] = [dict(r) for r in self.con.execute("SELECT * FROM order_items WHERE order_id=?", (o["order_id"],))]
            out.append(o)
        return out

    def integrity_report(self):
        """Comprobaciones globales usadas al final de cada escenario."""
        neg = self.con.execute("SELECT COUNT(*) FROM inventory WHERE stock < 0").fetchone()[0]
        dups = self.con.execute("SELECT COUNT(*) FROM (SELECT quote_id FROM orders GROUP BY quote_id HAVING COUNT(*)>1)").fetchone()[0]
        empty = self.con.execute("SELECT COUNT(*) FROM orders o WHERE NOT EXISTS "
                                 "(SELECT 1 FROM order_items i WHERE i.order_id=o.order_id)").fetchone()[0]
        return {"negative_stock": neg, "duplicate_orders": dups, "orders_without_items": empty}
