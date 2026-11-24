"""Recuperación híbrida sobre el catálogo.

Arquitectura (diseñada e implementada por el grupo):

    consulta ──► BM25 propio (scipy.sparse, stemming español) ──┐
             └─► denso multilingual-e5 (similitud coseno) ──────┤─► RRF ponderado ─► top-N ─► cross-encoder ─► ranking final
                                                                 (filtros de tienda: precio / stock se aplican después)

* ``BM25Index`` es también el **modelo base léxico** exigido por el enunciado.
* La fusión Reciprocal Rank Fusion evita calibrar escalas de puntuación distintas.
* El cross-encoder ``bge-reranker-v2-m3`` reordena solo los ``rerank_depth`` mejores
  (coste acotado) y es el componente usado en la ablación.
"""
import time
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from . import config as C
from .textutils import tokenize, normalize


# ---------------------------------------------------------------------------
# BM25 (implementación propia, vectorizada)
# ---------------------------------------------------------------------------
class BM25Index:
    def __init__(self, k1=1.2, b=0.75, title_boost=2):
        self.k1, self.b, self.title_boost = k1, b, title_boost

    def fit(self, titles, passages):
        # El título se repite ``title_boost`` veces: es el campo más informativo en ESCI.
        docs = [tokenize((t + " ") * self.title_boost + p) for t, p in zip(titles, passages)]
        vocab = {}
        rows, cols, vals = [], [], []
        for i, toks in enumerate(docs):
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            for t, c in counts.items():
                j = vocab.setdefault(t, len(vocab))
                rows.append(i); cols.append(j); vals.append(c)
        n_docs = len(docs)
        tf = sp.csr_matrix((vals, (rows, cols)), shape=(n_docs, len(vocab)), dtype=np.float32)
        dl = np.asarray(tf.sum(axis=1)).ravel()
        avgdl = dl.mean() if n_docs else 1.0
        df = np.bincount(tf.indices, minlength=len(vocab))
        idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        # Peso BM25 precomputado por (doc, término): idf * tf (k1+1) / (tf + k1 (1 - b + b dl/avgdl))
        tf = tf.tocoo()
        norm = self.k1 * (1 - self.b + self.b * dl[tf.row] / avgdl)
        w = idf[tf.col] * tf.data * (self.k1 + 1) / (tf.data + norm)
        self.W = sp.csc_matrix((w, (tf.row, tf.col)), shape=tf.shape, dtype=np.float32)
        self.vocab, self.idf, self.n_docs = vocab, idf, n_docs
        return self

    def scores(self, query, doc_idx=None):
        q = [self.vocab[t] for t in tokenize(query) if t in self.vocab]
        if not q:
            s = np.zeros(self.n_docs, dtype=np.float32)
        else:
            s = np.asarray(self.W[:, q].sum(axis=1)).ravel()
        return s if doc_idx is None else s[doc_idx]


# ---------------------------------------------------------------------------
# Índice denso
# ---------------------------------------------------------------------------
class DenseIndex:
    """Embeddings multilingual-e5 normalizados (producto escalar = coseno)."""

    def __init__(self, model_name=C.MODELS.embedder, device="cuda"):
        from sentence_transformers import SentenceTransformer
        import torch
        self.model = SentenceTransformer(model_name, device=device,
                                         model_kwargs={"torch_dtype": torch.float16})
        self.emb = None

    def fit(self, passages, batch_size=128, cache_path=None):
        if cache_path is not None:
            # La caché se identifica por el contenido: si cambia el catálogo, se recalcula
            import hashlib
            h = hashlib.md5("\n".join(passages).encode("utf-8")).hexdigest()[:12]
            cache_path = cache_path.with_name(f"{cache_path.stem}_{h}{cache_path.suffix}")
        if cache_path is not None and cache_path.exists():
            self.emb = np.load(cache_path)
            if len(self.emb) == len(passages):
                return self
        self.emb = self.model.encode([f"passage: {p}" for p in passages], batch_size=batch_size,
                                     normalize_embeddings=True, show_progress_bar=True,
                                     convert_to_numpy=True).astype(np.float32)
        if cache_path is not None:
            np.save(cache_path, self.emb)
        return self

    def encode_query(self, query):
        return self.model.encode([f"query: {query}"], normalize_embeddings=True,
                                 convert_to_numpy=True)[0].astype(np.float32)

    def scores(self, query, doc_idx=None):
        q = self.encode_query(query)
        E = self.emb if doc_idx is None else self.emb[doc_idx]
        return E @ q


# ---------------------------------------------------------------------------
# Re-ranker (cross-encoder)
# ---------------------------------------------------------------------------
class Reranker:
    def __init__(self, model_name=C.MODELS.reranker, device="cuda", max_length=512):
        from sentence_transformers import CrossEncoder
        import torch
        self.model = CrossEncoder(model_name, device=device, max_length=max_length,
                                  model_kwargs={"torch_dtype": torch.float16})

    def scores(self, query, passages, batch_size=32):
        if len(passages) == 0:
            return np.zeros(0, dtype=np.float32)
        pairs = [(query, p) for p in passages]
        return np.asarray(self.model.predict(pairs, batch_size=batch_size,
                                             show_progress_bar=False), dtype=np.float32)


# ---------------------------------------------------------------------------
# Fusión
# ---------------------------------------------------------------------------
def ranks_from_scores(scores):
    """Rango 1..n (1 = mejor) para cada posición del vector de puntuaciones."""
    order = np.argsort(-scores, kind="stable")
    r = np.empty_like(order)
    r[order] = np.arange(1, len(scores) + 1)
    return r


def rrf(rank_lists, weights, k=60):
    fused = np.zeros(len(rank_lists[0]), dtype=np.float64)
    for r, w in zip(rank_lists, weights):
        fused += w / (k + r)
    return fused


@dataclass
class SearchHit:
    product_id: str
    idx: int
    score: float
    bm25: float = 0.0
    dense: float = 0.0
    rerank: float = None
    evidence: str = ""


class HybridSearcher:
    def __init__(self, catalog, bm25, dense=None, reranker=None, cfg=None):
        self.cat = catalog.reset_index(drop=True)
        self.pid2idx = {p: i for i, p in enumerate(self.cat["product_id"])}
        self.passages = self.cat["passage"].tolist()
        self.bm25, self.dense, self.reranker = bm25, dense, reranker
        self.cfg = cfg or C.RetrievalConfig()
        self.last_timing = {}

    # -- etapa 1: puntuaciones de primer nivel ---------------------------------
    def first_stage(self, query, doc_idx=None):
        cfg = self.cfg
        n = self.bm25.n_docs if doc_idx is None else len(doc_idx)
        t0 = time.perf_counter()
        s_bm25 = self.bm25.scores(query, doc_idx) if cfg.use_bm25 else np.zeros(n, np.float32)
        t1 = time.perf_counter()
        use_dense = cfg.use_dense and self.dense is not None
        s_dense = self.dense.scores(query, doc_idx) if use_dense else np.zeros(n, np.float32)
        t2 = time.perf_counter()
        lists, weights = [], []
        if cfg.use_bm25:
            lists.append(ranks_from_scores(s_bm25)); weights.append(cfg.w_bm25)
        if use_dense:
            lists.append(ranks_from_scores(s_dense)); weights.append(cfg.w_dense)
        fused = rrf(lists, weights, cfg.rrf_k) if lists else np.zeros(n)
        self.last_timing.update(bm25_s=t1 - t0, dense_s=t2 - t1)
        return fused, s_bm25, s_dense

    # -- búsqueda completa --------------------------------------------------------
    def search(self, query, k=10, doc_idx=None, allowed=None):
        """Devuelve ``SearchHit`` ordenados.

        doc_idx: restringe la búsqueda a esos índices (p. ej. candidatos anotados).
        allowed: función idx -> bool para filtros de negocio (precio, stock), aplicada
                 antes del re-ranking para no desperdiciar el presupuesto del cross-encoder.
        """
        cfg = self.cfg
        idx = np.arange(self.bm25.n_docs) if doc_idx is None else np.asarray(doc_idx)
        fused, s_bm25, s_dense = self.first_stage(query, None if doc_idx is None else idx)
        order = np.argsort(-fused, kind="stable")
        depth = max(k, cfg.rerank_depth) if (cfg.use_reranker and self.reranker) else k
        if allowed is not None:
            # Filtro perezoso: se recorre el ranking solo hasta reunir ``depth`` candidatos válidos
            kept = []
            for o in order:
                if allowed(int(idx[o])):
                    kept.append(o)
                    if len(kept) >= depth:
                        break
            order = np.array(kept, dtype=int)
        top = order[:depth]
        t0 = time.perf_counter()
        rr = None
        if cfg.use_reranker and self.reranker is not None and len(top):
            rr = self.reranker.scores(query, [self.passages[idx[o]] for o in top])
            top = top[np.argsort(-rr, kind="stable")]
            rr = np.sort(rr)[::-1]
        self.last_timing["rerank_s"] = time.perf_counter() - t0
        hits = []
        for pos, o in enumerate(top[:k]):
            gi = int(idx[o])
            hits.append(SearchHit(
                product_id=self.cat.at[gi, "product_id"], idx=gi,
                score=float(rr[pos]) if rr is not None else float(fused[o]),
                bm25=float(s_bm25[o]), dense=float(s_dense[o]),
                rerank=float(rr[pos]) if rr is not None else None,
                evidence=best_evidence(query, self.passages[gi]),
            ))
        return hits

    def rank_candidates(self, query, candidate_pids):
        """Ordena una lista cerrada de candidatos (protocolo de evaluación ESCI Task 1)."""
        idx = [self.pid2idx[p] for p in candidate_pids]
        hits = self.search(query, k=len(idx), doc_idx=idx)
        return [h.product_id for h in hits]


def best_evidence(query, passage, max_len=220):
    """Fragmento del texto del producto con mayor solapamiento léxico con la consulta.

    Se muestra al LLM como evidencia: las recomendaciones deben apoyarse en texto
    realmente recuperado, no en conocimiento paramétrico del modelo.
    """
    q = set(tokenize(query))
    best, best_s = passage[:max_len], -1
    for sent in [s.strip() for s in passage.replace(";", ".").split(".") if s.strip()]:
        s = len(q & set(tokenize(sent)))
        if s > best_s:
            best, best_s = sent, s
    return best[:max_len]
