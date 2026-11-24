"""Evaluación: recuperación (base léxica, híbrido, ablación), escenarios, voz, TTS y latencia."""
import itertools
import json
import time
from dataclasses import replace

import numpy as np
import pandas as pd

from . import config as C
from .metrics import ndcg_at_k, recall_at_k, paired_bootstrap, wer, cer, entity_errors
from .retrieval import ranks_from_scores, rrf

# Paleta categórica validada (slots 1-3 pasan todas las parejas en CVD) + tintas neutras
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------------------
# Recuperación
# ---------------------------------------------------------------------------
SYSTEMS = {
    # nombre: (use_bm25, use_dense, use_reranker)
    "BM25 (base léxica)": (True, False, False),
    "Denso e5": (False, True, False),
    "Híbrido RRF (sin re-ranker)": (True, True, False),
    "Denso + re-ranker (sin BM25)": (False, True, True),
    "BM25 + re-ranker (sin denso)": (True, False, True),
    "Sistema completo (RRF + re-ranker)": (True, True, True),
}


class RetrievalEvaluator:
    """Evalúa muchas configuraciones reutilizando puntuaciones cacheadas por consulta.

    mode='candidates': ordena solo los candidatos anotados (protocolo pedido: nDCG@10 sobre candidatos).
    mode='catalog'   : busca en las 15 000 fichas; los no anotados cuentan como ganancia 0
                       (métrica más exigente y más parecida al uso real del agente).
    """

    def __init__(self, searcher, queries, qrels):
        self.s = searcher
        self.queries = queries.set_index("query_id")
        self.gains = {q: dict(zip(g.product_id, g.gain)) for q, g in qrels.groupby("query_id")}
        self.cache, self.rr_cache = {}, {}

    def _first(self, qid, mode):
        key = (qid, mode)
        if key not in self.cache:
            query = self.queries.at[qid, "query"]
            if mode == "candidates":
                idx = np.array([self.s.pid2idx[p] for p in self.gains[qid]])
                # Orden aleatorio fijo: los empates (p. ej. BM25 = 0) no deben heredar el orden de las
                # filas de ESCI, que podría correlacionar con la etiqueta
                idx = np.random.default_rng(C.SEED + int(qid)).permutation(idx)
            else:
                idx = np.arange(self.s.bm25.n_docs)
            t0 = time.perf_counter()
            b = self.s.bm25.scores(query, idx if mode == "candidates" else None)
            t1 = time.perf_counter()
            d = self.s.dense.scores(query, idx if mode == "candidates" else None)
            t2 = time.perf_counter()
            self.cache[key] = (idx, b, d, ranks_from_scores(b), ranks_from_scores(d), t1 - t0, t2 - t1)
        return self.cache[key]

    def _rerank(self, qid, gidx):
        query = self.queries.at[qid, "query"]
        missing = [g for g in gidx if (qid, g) not in self.rr_cache]
        if missing:
            sc = self.s.reranker.scores(query, [self.s.passages[g] for g in missing])
            for g, v in zip(missing, sc):
                self.rr_cache[(qid, g)] = float(v)
        return np.array([self.rr_cache[(qid, g)] for g in gidx])

    def rank(self, qid, cfg, mode):
        idx, b, d, rb, rd, _, _ = self._first(qid, mode)
        lists, w = [], []
        if cfg.use_bm25:
            lists.append(rb); w.append(cfg.w_bm25)
        if cfg.use_dense:
            lists.append(rd); w.append(cfg.w_dense)
        fused = rrf(lists, w, cfg.rrf_k)
        order = np.argsort(-fused, kind="stable")
        if cfg.use_reranker:
            top, rest = order[:cfg.rerank_depth], order[cfg.rerank_depth:]
            rr = self._rerank(qid, idx[top])
            order = np.concatenate([top[np.argsort(-rr, kind="stable")], rest])
        return [self.s.cat.at[int(idx[o]), "product_id"] for o in order[:10]]

    def evaluate(self, cfg, split="test", mode="candidates"):
        qids = self.queries.index[self.queries["split"] == split]
        nd, rc = [], []
        for q in qids:
            ranked = self.rank(q, cfg, mode)
            nd.append(ndcg_at_k(ranked, self.gains[q], 10))
            rc.append(recall_at_k(ranked, self.gains[q], 10))
        return {"ndcg@10": float(np.mean(nd)), "recall_E@10": float(np.mean(rc)),
                "per_query": dict(zip(qids, nd))}

    def compare_systems(self, base_cfg, split="test", modes=("candidates", "catalog")):
        rows, per_q = [], {}
        for name, (ub, ud, ur) in SYSTEMS.items():
            cfg = replace(base_cfg, use_bm25=ub, use_dense=ud, use_reranker=ur)
            for mode in modes:
                r = self.evaluate(cfg, split, mode)
                rows.append({"sistema": name, "modo": mode, "nDCG@10": r["ndcg@10"], "Recall_E@10": r["recall_E@10"]})
                per_q[(name, mode)] = r["per_query"]
        df = pd.DataFrame(rows)
        # Significancia frente a la base léxica (bootstrap pareado por consulta)
        sig = []
        for (name, mode), pq in per_q.items():
            if name.startswith("BM25 (base"):
                continue
            base = per_q[("BM25 (base léxica)", mode)]
            q = list(base)
            bs = paired_bootstrap([base[x] for x in q], [pq[x] for x in q])
            sig.append({"sistema": name, "modo": mode, "Δ vs BM25": bs["diff"],
                        "IC95": f"[{bs['ci95'][0]:+.3f}, {bs['ci95'][1]:+.3f}]", "p": bs["p_value"]})
        return df, pd.DataFrame(sig), per_q

    def tune_on_dev(self, base_cfg, mode="candidates"):
        """Ajuste de hiperparámetros SOLO con consultas de desarrollo (split=train)."""
        grid = []
        for wb, k in itertools.product([0.5, 0.75, 1.0, 1.5], [20, 60]):
            cfg = replace(base_cfg, w_bm25=wb, rrf_k=k, use_reranker=False)
            grid.append({"w_bm25": wb, "rrf_k": k, "nDCG@10_dev": self.evaluate(cfg, "dev", mode)["ndcg@10"]})
        g = pd.DataFrame(grid).sort_values("nDCG@10_dev", ascending=False)
        best = g.iloc[0]
        cfg = replace(base_cfg, w_bm25=float(best.w_bm25), rrf_k=int(best.rrf_k))
        depth_rows = []
        for depth in [10, 20, 30, 50]:
            c2 = replace(cfg, rerank_depth=depth, use_reranker=True)
            depth_rows.append({"rerank_depth": depth,
                               "nDCG@10_dev(catalogo)": self.evaluate(c2, "dev", "catalog")["ndcg@10"]})
        d = pd.DataFrame(depth_rows)
        # Profundidad: la menor cuyo nDCG está a <0.005 del mejor (compromiso calidad/latencia)
        bestv = d["nDCG@10_dev(catalogo)"].max()
        depth = int(d[d["nDCG@10_dev(catalogo)"] >= bestv - 0.005]["rerank_depth"].min())
        return replace(cfg, rerank_depth=depth), g, d

    def latency_table(self, cfg, split="test", n=50):
        qids = list(self.queries.index[self.queries["split"] == split])[:n]
        rows = []
        for q in qids:
            query = self.queries.at[q, "query"]
            t0 = time.perf_counter()
            self.s.cfg = cfg
            self.s.search(query, k=10)
            rows.append({"total_ms": 1000 * (time.perf_counter() - t0),
                         **{k: 1000 * v for k, v in self.s.last_timing.items()}})
        return pd.DataFrame(rows).describe().loc[["mean", "50%", "max"]].round(1)


def plot_systems(df, path=None):
    import matplotlib.pyplot as plt
    modes = list(df["modo"].unique())
    fig, axes = plt.subplots(1, len(modes), figsize=(6.2 * len(modes), 3.8), sharey=True)
    axes = np.atleast_1d(axes)
    order = list(SYSTEMS)
    for ax, mode in zip(axes, modes):
        d = df[df["modo"] == mode].set_index("sistema").loc[order]
        colors = [PALETTE[1] if n.startswith("BM25 (base") else PALETTE[0] if n.startswith("Sistema") else "#9b9a95"
                  for n in d.index]
        y = np.arange(len(d))
        ax.barh(y, d["nDCG@10"], color=colors, height=0.55, edgecolor=SURFACE, linewidth=2)
        for yi, v in zip(y, d["nDCG@10"]):
            ax.text(v + 0.005, yi, f"{v:.3f}", va="center", color=INK, fontsize=9)
        ax.set_yticks(y, d.index, color=INK)
        ax.invert_yaxis()
        ax.set_title({"candidates": "nDCG@10 sobre candidatos anotados",
                      "catalog": "nDCG@10 sobre el catálogo completo"}[mode], color=INK, fontsize=11, loc="left")
        ax.set_xlim(0, min(1.0, d["nDCG@10"].max() * 1.18))
        _style(ax)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    return fig


def error_analysis(ev, cfg, split="test", mode="candidates", n=5):
    """Los n mejores y n peores casos del sistema completo, con su top-3 y etiquetas ESCI."""
    res = ev.evaluate(cfg, split, mode)["per_query"]
    base_cfg = replace(cfg, use_dense=False, use_reranker=False)
    base = ev.evaluate(base_cfg, split, mode)["per_query"]
    labels = {}
    for q, g in ev.gains.items():
        labels[q] = {p: {1.0: "E", 0.1: "S", 0.01: "C", 0.0: "I"}[v] for p, v in g.items()}
    titles = ev.s.cat.set_index("product_id")["title"]
    rows = []
    srt = sorted(res, key=res.get)
    for kind, qs in [("acierto", srt[::-1][:n]), ("fallo", srt[:n])]:
        for q in qs:
            ranked = ev.rank(q, cfg, mode)[:3]
            rows.append({"tipo": kind, "query_id": q, "consulta": ev.queries.at[q, "query"],
                         "nDCG@10": round(res[q], 3), "nDCG@10_BM25": round(base[q], 3),
                         "top3": " | ".join(f"[{labels[q].get(p, '·')}] {titles[p][:60]}" for p in ranked),
                         "n_E": sum(1 for v in labels[q].values() if v == "E"), "n_cand": len(labels[q])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Escenarios y voz
# ---------------------------------------------------------------------------
def scenario_table(results):
    rows = [{"id": r["id"], "escenario": r["title"], "categoría": r["category"], "ok": "✅" if r["passed"] else "❌",
             "turnos": len(r["turns"]), "operaciones": len(r["ops"]),
             "fallos": "; ".join(r["failures"]), "incumplimientos": ", ".join(r["violations"])} for r in results]
    df = pd.DataFrame(rows)
    summary = {"escenarios": len(results), "completados_ok": int(sum(r["passed"] for r in results)),
               "porcentaje_ok": round(100 * np.mean([r["passed"] for r in results]), 1),
               "incumplimientos_totales": int(sum(len(r["violations"]) for r in results)),
               "incumplimientos_por_tipo": pd.Series([v for r in results for v in r["violations"]]).value_counts().to_dict()}
    return df, summary


def asr_error_table(voice_results, scenarios_by_id):
    """WER/CER y errores de entidades (cantidades, importes, productos) por turno de voz."""
    rows = []
    for vr in voice_results:
        scn = scenarios_by_id[vr["id"]]
        gold_turns = scn.voice_turns or scn.turns
        for i, t in enumerate(vr["turns"]):
            gold = gold_turns[i]
            e = entity_errors(gold, t["asr_raw"], scn.product_terms if i == 0 else ())
            rows.append({"escenario": vr["id"], "turno": i + 1, "referencia": gold, "asr": t["asr_raw"],
                         "WER": wer(gold, t["asr_raw"]), "CER": cer(gold, t["asr_raw"]),
                         "corregido": t.get("corrected", False), **e})
    df = pd.DataFrame(rows)
    tot = {"WER_medio": df["WER"].mean(), "CER_medio": df["CER"].mean(),
           "errores_cantidad": f"{df.qty_err.sum()}/{df.qty_ref.sum()}",
           "errores_importe": f"{df.amount_err.sum()}/{df.amount_ref.sum()}",
           "errores_producto": f"{df.product_err.sum()}/{df.product_ref.sum()}"}
    return df, tot


def latency_breakdown(voice_results):
    rows = []
    for vr in voice_results:
        for i, t in enumerate(vr["turns"]):
            rows.append({"escenario": vr["id"], "turno": i + 1, **t["latency"]})
    df = pd.DataFrame(rows)
    df["agente_otros_s"] = df["agente_total_s"] - df["agente_llm_s"] - df["agente_herramientas_s"]
    return df


def plot_latency(df, path=None):
    import matplotlib.pyplot as plt
    stages = [("asr_s", "ASR"), ("agente_llm_s", "LLM (agente)"), ("agente_herramientas_s", "Herramientas + RAG"),
              ("tts_s", "TTS")]
    m = df[[s for s, _ in stages]].mean()
    fig, ax = plt.subplots(figsize=(8, 2.4))
    left = 0
    for (s, lab), c in zip(stages, [PALETTE[0], PALETTE[1], PALETTE[2], "#9b9a95"]):
        ax.barh([0], [m[s]], left=left, color=c, height=0.45, edgecolor=SURFACE, linewidth=2, label=lab)
        if m[s] > 0.6:
            ax.text(left + m[s] / 2, 0, f"{m[s]:.1f} s", ha="center", va="center", color="white", fontsize=9)
        left += m[s]
    ax.set_yticks([])
    ax.set_xlabel("segundos (media por turno, desde fin de la grabación)", color=INK2)
    ax.set_title(f"Latencia por etapa — total medio {df['total_s'].mean():.1f} s", color=INK, loc="left", fontsize=11)
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.45), labelcolor=INK2)
    _style(ax)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    return fig


def tts_quality(asr, spk, tts, reference_wav, reference_text, voice_results, other_voice_wav=None):
    """Inteligibilidad (WER del ASR sobre la voz sintetizada) y semejanza con la referencia."""
    from .speech import load_audio, text_overlap
    ref = load_audio(reference_wav)
    half = len(ref) // 2
    rows = []
    for vr in voice_results:
        for i, t in enumerate(vr["turns"]):
            if not t.get("audio_out"):
                continue
            wav = load_audio(t["audio_out"])
            hyp, _ = asr.transcribe(wav)
            rows.append({"escenario": vr["id"], "turno": i + 1, "texto": t["tts_text"][:80],
                         "WER_inteligibilidad": wer(t["tts_text"], hyp),
                         "similitud_referencia": spk.similarity(ref, wav),
                         "solapamiento_trigramas_ref": text_overlap(t["tts_text"], reference_text)})
    df = pd.DataFrame(rows)
    bounds = {"ref_mitad_vs_mitad (cota sup.)": spk.similarity(ref[:half], ref[half:])}
    if other_voice_wav is not None:
        bounds["otra_voz_vs_ref (cota inf.)"] = spk.similarity(ref, load_audio(other_voice_wav))
    return df, bounds


def write_report(path, sections):
    """Escribe RESULTADOS.md con las tablas generadas en la ejecución."""
    lines = ["# Resultados del Laboratorio 4 (generado automáticamente)", "",
             f"_Generado: {time.strftime('%Y-%m-%d %H:%M')}_", ""]
    for title, content in sections:
        lines.append(f"## {title}\n")
        if isinstance(content, pd.DataFrame):
            lines.append(content.to_markdown(index=False, floatfmt=".3f"))
        elif isinstance(content, dict):
            lines.append("```json\n" + json.dumps(content, indent=2, ensure_ascii=False, default=str) + "\n```")
        else:
            lines.append(str(content))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
