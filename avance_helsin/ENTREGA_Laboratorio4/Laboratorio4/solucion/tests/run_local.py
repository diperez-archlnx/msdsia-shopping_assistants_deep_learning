"""Ejecución local por etapas (fuera de Colab) para probar el pipeline: python tests/run_local.py <etapa>."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LAB4_BASE", str(ROOT.parent / "work_local"))
os.environ.setdefault("LAB4_STORE", str(ROOT.parent / "work_local" / "store"))
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import psutil

from lab4 import config as C

C.ensure_dirs()
PROC = psutil.Process()
LOG = C.RESULTS_DIR / "run_local_log.jsonl"


def mark(stage, t0, **kw):
    rec = {"etapa": stage, "seg": round(time.perf_counter() - t0, 1),
           "ram_proceso_gb": round(PROC.memory_info().rss / 1e9, 2), **kw}
    try:
        import torch
        if torch.cuda.is_available():
            rec["vram_max_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
    except ImportError:
        pass
    print("⏱", json.dumps(rec, ensure_ascii=False, default=str))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def stage_data():
    from lab4 import data
    t0 = time.perf_counter(); data.download_esci(); mark("descarga_esci", t0)
    t0 = time.perf_counter(); cat, q, qr = data.prepare_data(); mark("preparacion", t0, productos=len(cat))


def build_searcher(reg=None):
    from lab4 import data
    from lab4.retrieval import BM25Index, DenseIndex, Reranker, HybridSearcher
    from lab4.pipeline import ModelRegistry
    reg = reg or ModelRegistry()
    cat, q, qr = data.load_prepared()
    t0 = time.perf_counter()
    bm25 = BM25Index(C.RETRIEVAL.bm25_k1, C.RETRIEVAL.bm25_b).fit(cat.title.tolist(), cat.passage.tolist())
    mark("bm25_fit", t0, vocab=len(bm25.vocab))
    dense = reg.load("embedder", lambda: DenseIndex())
    t0 = time.perf_counter(); dense.fit(cat.passage.tolist(), cache_path=C.INDEX_DIR / "e5_base_passages.npy")
    mark("embeddings", t0)
    reranker = reg.load("reranker", lambda: Reranker())
    cfg_path = C.RESULTS_DIR / "best_cfg.json"
    cfg = C.RETRIEVAL
    if cfg_path.exists():
        from dataclasses import replace
        cfg = replace(C.RETRIEVAL, **json.loads(cfg_path.read_text()))
    return HybridSearcher(cat, bm25, dense, reranker, cfg), cat, q, qr, reg


def stage_retrieval():
    from dataclasses import asdict
    from lab4 import evaluation as E
    from lab4.textutils import normalize
    from lab4.scenarios import kw_pids
    from lab4.data import SCENARIO_KEYWORDS
    searcher, cat, q, qr, reg = build_searcher()
    print("Productos por palabra clave de escenario:", {k: len(kw_pids(cat, k)) for k in SCENARIO_KEYWORDS})
    for h in searcher.search("auriculares bluetooth para correr", k=5):
        print(f"  {h.score:7.3f} {cat.loc[h.idx, 'title'][:80]}")
    ev = E.RetrievalEvaluator(searcher, q, qr)
    t0 = time.perf_counter(); best, g, d = ev.tune_on_dev(C.RETRIEVAL); mark("ajuste_dev", t0)
    print(g.head(8).to_string()); print(d.to_string()); print("elegida:", best)
    (C.RESULTS_DIR / "best_cfg.json").write_text(json.dumps(
        {k: v for k, v in asdict(best).items() if k in ("w_bm25", "rrf_k", "rerank_depth")}))
    t0 = time.perf_counter(); df, sig, _ = ev.compare_systems(best, "test"); mark("evaluacion_test", t0)
    print(df.pivot(index="sistema", columns="modo", values="nDCG@10").loc[list(E.SYSTEMS)].round(4).to_string())
    print(sig.round(4).to_string())
    df.to_csv(C.RESULTS_DIR / "recuperacion_test.csv", index=False)
    sig.to_csv(C.RESULTS_DIR / "significancia.csv", index=False)
    E.plot_systems(df, C.RESULTS_DIR / "ndcg_sistemas.png")
    err = E.error_analysis(ev, best, "test", "candidates", 5)
    err.to_csv(C.RESULTS_DIR / "aciertos_fallos_recuperacion.csv", index=False)
    print(err[["tipo", "consulta", "nDCG@10", "nDCG@10_BM25", "top3"]].to_string())
    for name, flags in [("BM25", (True, False, False)), ("Completo", (True, True, True))]:
        from dataclasses import replace
        lt = ev.latency_table(replace(best, use_bm25=flags[0], use_dense=flags[1], use_reranker=flags[2]))
        print(name, "latencia (ms)\n", lt.to_string())
    print(reg.load_report)


def load_llm(reg):
    from lab4.llm import LocalLLM
    local = os.environ.get("LAB4_LLM_DIR")
    if local and Path(local, "model-00001-of-00005.safetensors").exists():
        C.MODELS.llm = local          # copia local descargada con curl (reanudable)
    try:
        return reg.load("llm", lambda: LocalLLM(C.MODELS.llm))
    except Exception as e:
        print("Fallo LLM principal:", repr(e)[:300])
        return reg.load("llm", lambda: LocalLLM(C.MODELS.llm_fallback))


def base_store(cat):
    from lab4.store import Store
    st = Store(C.STORE_DIR / "store.db")
    st.reset(cat.product_id.tolist(), seed=C.SEED)
    st.snapshot("base")
    return st


def stage_agent():
    from lab4.agent import ShoppingAgent
    searcher, cat, q, qr, reg = build_searcher()
    llm = load_llm(reg)
    store = base_store(cat)
    agent = ShoppingAgent(llm, store, searcher, cat, session_id="demo", trace=True)
    for u in ["Hola, busco una mochila para portátil, como mucho 40 euros.", "¿La primera es impermeable?",
              "Añade una de la primera y prepara la cotización.", "Sí, confirmo."]:
        t0 = time.perf_counter()
        r = agent.handle(u)
        print("👤", u, "\n🤖", r["response"], "\n", {k: round(v, 2) for k, v in r["timing"].items()})
        mark("turno_agente", t0, llm_calls=r["timing"]["llm_calls"])
    print(store.orders("demo"))
    print(reg.load_report)


def stage_scenarios(ids=None):
    from lab4 import evaluation as E
    from lab4.scenarios import SCENARIOS, run_scenario
    import lab4.agent as A
    searcher, cat, q, qr, reg = build_searcher()
    llm = load_llm(reg)
    store = base_store(cat)
    sel = [s for s in SCENARIOS if not ids or s.id in ids]
    t0 = time.perf_counter()
    res = []
    for s in sel:
        print(f"━━━━ {s.id} · {s.title}")
        t1 = time.perf_counter()
        res.append(run_scenario(s, llm, store, searcher, cat))
        mark(f"escenario_{s.id}", t1, ok=res[-1]["passed"])
    mark("escenarios_texto", t0)
    json.dump(res, open(C.RESULTS_DIR / "escenarios_texto.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    df, summ = E.scenario_table(res)
    print(df.to_string()); print(json.dumps(summ, ensure_ascii=False, indent=1))
    if ids:
        return
    from dataclasses import replace
    t0 = time.perf_counter()
    abl = [run_scenario(s, llm, store, searcher, cat, verbose=False, agent_cfg=replace(C.AGENT, use_rules=False))
           for s in sel]
    mark("ablacion_guardas", t0)
    json.dump(abl, open(C.RESULTS_DIR / "escenarios_ablacion.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    adf, asumm = E.scenario_table(abl)
    print(adf.to_string()); print("ABLACIÓN:", json.dumps(asumm, ensure_ascii=False))


def stage_voice():
    """Prueba del pipeline de voz con audios SINTÉTICOS (voces de stock de XTTS).

    Solo valida la integración y mide latencias; la entrega requiere grabaciones reales del grupo.
    """
    import re
    import soundfile as sf
    from lab4 import evaluation as E
    from lab4.metrics import entity_errors
    from lab4.pipeline import VoiceAssistant
    from lab4.scenarios import SCENARIOS, run_scenario
    from lab4.speech import ASR, VoiceTTS, SpeakerSimilarity, load_audio
    import torch
    # Límite duro: si se supera, error explícito en vez de paginar VRAM a RAM (lentitud extrema en Windows)
    torch.cuda.set_per_process_memory_fraction(0.90)
    searcher, cat, q, qr, reg = build_searcher()
    llm = load_llm(reg)
    store = base_store(cat)
    asr = reg.load("asr", lambda: ASR())
    ad = C.AUDIO_DIR / "sinteticos"; ad.mkdir(parents=True, exist_ok=True)
    ref_text = ("Hola, soy integrante del grupo del laboratorio cuatro de aprendizaje profundo. Esta grabación se usa "
                "únicamente como referencia para clonar mi voz con fines académicos. Leo este párrafo con calma, en un "
                "lugar silencioso, para que el modelo capture bien el timbre, el ritmo y la entonación de mi forma de hablar.")
    voice = [s for s in SCENARIOS if s.voice]
    needed = [ad / "referencia.wav", ad / "otra_voz.wav"] + [
        ad / f"{s.id}_t{i+1}.wav" for s in voice for i in range(len(s.voice_turns or s.turns))]
    if all(p.exists() for p in needed):
        stock = None          # audios de prueba ya generados: no se carga un segundo XTTS (ahorra ~2 GB de VRAM)
    else:
        from TTS.api import TTS
        t0 = time.perf_counter()
        stock = TTS(C.MODELS.tts).to("cuda")
        mark("carga_xtts_stock", t0)
    ref = ad / "referencia.wav"
    if not ref.exists():
        stock.tts_to_file(text=ref_text, speaker="Ana Florence", language="es", file_path=str(ref))
    other = ad / "otra_voz.wav"
    if not other.exists():
        stock.tts_to_file(text="Buenos días, esta es una voz diferente usada como control.", speaker="Damien Black",
                          language="es", file_path=str(other))
    voice = [s for s in SCENARIOS if s.voice]
    for s in voice:
        for i, t in enumerate(s.voice_turns or s.turns):
            p = ad / f"{s.id}_t{i+1}.wav"
            if not p.exists():
                stock.tts_to_file(text=t, speaker="Claribel Dervla", language="es", file_path=str(p))
    del stock
    from lab4.pipeline import free_memory; free_memory()
    tts = reg.load("tts", lambda: VoiceTTS(ref))
    spk = reg.load("speaker_verif", lambda: SpeakerSimilarity())

    def make_fn(s, review):
        def fn(agent, i, gold):
            va = VoiceAssistant(asr, agent, tts, audio_dir=ad / "respuestas")
            wav = ad / f"{s.id}_t{i+1}.wav"
            perturb, correction, asr_result = s.asr_perturb.get(i), None, None
            if review:
                raw, asr_s = asr.transcribe(wav); asr_result = (raw, asr_s)
                hyp = re.sub(perturb[0], perturb[1], raw, flags=re.I) if perturb else raw
                e = entity_errors(gold, hyp, s.product_terms if i == 0 else ())
                print(f"   📝 mostrado: «{hyp}»")
                if e["qty_err"] or e["amount_err"] or e["product_err"]:
                    print(f"   ✏️ corregido → «{gold}»"); correction = gold
            r = va.turn(wav, t_end=time.perf_counter(), correction=correction, perturb=perturb,
                        tag=f"{s.id}_t{i+1}", asr_result=asr_result)
            r["gold"] = gold
            print(f"   ⏱ {s.id} t{i+1}: " + ", ".join(f"{k}={v:.2f}" for k, v in r["latency"].items()) + f" | GPU {r['gpu']}", flush=True)
            return r
        return fn

    vres, gres = [], []
    t0 = time.perf_counter()
    for s in voice:
        print(f"━━━━ VOZ {s.id}")
        vres.append(run_scenario(s, llm, store, searcher, cat, turns=s.voice_turns or s.turns,
                                 turn_fn=make_fn(s, s.id == "S06")))
        gres.append(run_scenario(s, llm, store, searcher, cat, turns=s.voice_turns or s.turns, verbose=False))
    mark("escenarios_voz", t0)
    json.dump(vres, open(C.RESULTS_DIR / "escenarios_voz.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    for v, g in zip(vres, gres):
        print(v["id"], "voz:", v["passed"], v["failures"] + v["violations"], "| gold:", g["passed"])
    SCN = {s.id: s for s in SCENARIOS}
    adf, tot = E.asr_error_table(vres, SCN)
    print(adf[["escenario", "turno", "asr", "WER", "qty_err", "amount_err", "product_err"]].to_string())
    print(json.dumps(tot, default=float, ensure_ascii=False))
    tdf, bounds = E.tts_quality(asr, spk, tts, ref, ref_text, vres, other_voice_wav=other)
    print(tdf.describe().round(3).to_string()); print(bounds)
    lat = E.latency_breakdown(vres)
    print(lat.describe().loc[["mean", "50%", "max"]].round(2).to_string())
    print("primer turno vs resto:", round(lat.total_s.iloc[0], 2), round(lat.total_s.iloc[1:].mean(), 2))
    E.plot_latency(lat, C.RESULTS_DIR / "latencia.png")
    lat.to_csv(C.RESULTS_DIR / "latencia.csv", index=False)
    print(json.dumps(reg.load_report, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 2:
        globals()["stage_" + sys.argv[1]](sys.argv[2].split(","))
        sys.exit()
    globals()["stage_" + sys.argv[1]]()
