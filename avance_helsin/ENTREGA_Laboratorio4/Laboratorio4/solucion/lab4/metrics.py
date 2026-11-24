"""Métricas: nDCG@10 con ganancias ESCI, WER/CER y errores de entidades del ASR."""
import re

import numpy as np

from .textutils import normalize, extract_amounts, extract_quantities, tokenize, spanish_numbers_to_digits


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
def dcg(gains):
    gains = np.asarray(gains, dtype=np.float64)
    return float(np.sum(gains / np.log2(np.arange(2, len(gains) + 2))))


def ndcg_at_k(ranked_pids, gain_of, k=10):
    """nDCG@k con ganancias lineales E=1, S=0.1, C=0.01, I=0.

    ``gain_of``: dict product_id -> ganancia, con TODOS los candidatos anotados
    de la consulta (el ideal se calcula sobre ellos). Los productos no anotados
    (solo posibles en búsqueda sobre el catálogo completo) cuentan como 0.
    """
    g = [gain_of.get(p, 0.0) for p in ranked_pids[:k]]
    ideal = sorted(gain_of.values(), reverse=True)[:k]
    idcg = dcg(ideal)
    return dcg(g) / idcg if idcg > 0 else 0.0


def recall_at_k(ranked_pids, gain_of, k=10, label_gain=1.0):
    rel = {p for p, g in gain_of.items() if g >= label_gain}
    if not rel:
        return 0.0
    return len(rel & set(ranked_pids[:k])) / len(rel)


def paired_bootstrap(a, b, n=5000, seed=0):
    """IC 95 % de la diferencia media (b - a) y p-valor unilateral aproximado."""
    a, b = np.asarray(a), np.asarray(b)
    rng = np.random.default_rng(seed)
    d = b - a
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)])
    return {"diff": float(d.mean()), "ci95": (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))),
            "p_value": float((boots <= 0).mean())}


# ---------------------------------------------------------------------------
# Voz
# ---------------------------------------------------------------------------
def _norm_words(text):
    t = spanish_numbers_to_digits(text)
    t = normalize(t)
    t = re.sub(r"[^\w\s.,€]", " ", t)
    t = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", t)   # conserva decimales 12,50
    return t.split()


def edit_distance(ref, hyp):
    d = np.arange(len(hyp) + 1)
    for i in range(1, len(ref) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(hyp) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev = cur
    return int(d[len(hyp)])


def wer(ref, hyp):
    r, h = _norm_words(ref), _norm_words(hyp)
    return edit_distance(r, h) / max(1, len(r))


def cer(ref, hyp):
    r, h = list(" ".join(_norm_words(ref))), list(" ".join(_norm_words(hyp)))
    return edit_distance(r, h) / max(1, len(r))


def entity_errors(ref, hyp, product_terms=()):
    """Errores de transcripción en cantidades, importes y productos.

    product_terms: palabras clave de producto que aparecen en la referencia
    (p. ej. ["mochila", "botella"]); se compara su presencia tras stemming.
    """
    def multiset_diff(a, b):
        b = list(b); miss = 0
        for x in a:
            if x in b:
                b.remove(x)
            else:
                miss += 1
        return miss

    ra, ha = extract_amounts(ref), extract_amounts(hyp)
    rq, hq = extract_quantities(ref), extract_quantities(hyp)
    rs, hs = set(tokenize(" ".join(product_terms))), set(tokenize(hyp))
    return {
        "amount_ref": len(ra), "amount_err": multiset_diff(ra, ha),
        "qty_ref": len(rq), "qty_err": multiset_diff(rq, hq),
        "product_ref": len(rs), "product_err": len(rs - hs),
    }
