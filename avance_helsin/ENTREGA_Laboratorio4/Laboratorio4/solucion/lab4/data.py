"""Preparación de datos: catálogo, consultas de desarrollo/evaluación y qrels ESCI.

Decisiones:
* Se usa la versión reducida (``small_version == 1``, Task 1 de ranking) y ``product_locale == 'es'``.
* La partición se hace por ``query_id`` respetando el ``split`` original:
  ``train`` -> consultas de desarrollo (ajuste de hiperparámetros) y ``test`` -> evaluación.
* El catálogo contiene TODOS los productos anotados de las consultas elegidas
  y se completa con distractores del mismo locale (productos anotados para otras
  consultas españolas), hasta ``CATALOG_SIZE``. Así la búsqueda sobre todo el
  catálogo es realista y no trivial.
* Las etiquetas ESCI se guardan en ``qrels.parquet`` separadas del catálogo: el
  agente y el índice NUNCA las leen; solo las usa el módulo de evaluación.
"""
import json
import urllib.request

import numpy as np
import pandas as pd

from . import config as C
from .textutils import strip_html

PRODUCT_COLS = ["product_id", "product_title", "product_description",
                "product_bullet_point", "product_brand", "product_color", "product_locale"]


def download_esci(force=False):
    C.ensure_dirs()
    for name in C.ESCI_FILES:
        dst = C.RAW_DIR / name
        if dst.exists() and dst.stat().st_size > 10_000 and not force:
            continue
        print(f"Descargando {name} ...")
        urllib.request.urlretrieve(C.ESCI_URL + name, dst)
        print(f"  {dst.stat().st_size / 1e6:.1f} MB")
        if dst.stat().st_size < 10_000:
            raise RuntimeError(f"{name} parece un puntero Git LFS; revise la URL de descarga")


def load_examples():
    ex = pd.read_parquet(C.RAW_DIR / "shopping_queries_dataset_examples.parquet")
    ex = ex[(ex["small_version"] == 1) & (ex["product_locale"] == C.LOCALE)].copy()
    return ex


def load_products_es():
    # El parquet de productos ocupa ~1.1 GB: se filtra por locale al leer para
    # no cargar los productos de EE. UU. y Japón en la RAM de Colab.
    return pd.read_parquet(
        C.RAW_DIR / "shopping_queries_dataset_products.parquet",
        columns=PRODUCT_COLS,
        filters=[("product_locale", "==", C.LOCALE)],
    )


def _select_queries(ex, split, n, rng):
    g = ex[ex["split"] == split].groupby("query_id").agg(
        query=("query", "first"),
        n=("product_id", "size"),
        n_exact=("esci_label", lambda s: int((s == "E").sum())),
    ).reset_index()
    g = g[(g["n"] >= C.MIN_JUDGEMENTS) & (g["n_exact"] >= 1)]
    ids = rng.choice(g["query_id"].values, size=min(n, len(g)), replace=False)
    return g[g["query_id"].isin(ids)].copy()


def build_passage(row, max_chars=C.RETRIEVAL.max_passage_chars):
    parts = [row["title"]]
    if row["brand"]:
        parts.append(f"Marca: {row['brand']}")
    if row["color"]:
        parts.append(f"Color: {row['color']}")
    if row["bullets"]:
        parts.append(row["bullets"])
    if row["description"]:
        parts.append(row["description"])
    return ". ".join(p for p in parts if p)[:max_chars]


# Tipos de producto que usan los escenarios operativos (scenarios.py). Se garantiza que el
# catálogo contenga al menos MIN_PER_KEYWORD productos de cada uno, sustituyendo distractores
# aleatorios (nunca productos anotados), para que los escenarios sean reproducibles.
SCENARIO_KEYWORDS = ["botella", "cargador", "cuaderno", "boligrafo", "auricular", "taza", "lampara",
                     "cable", "mochila", "raton", "alfombrilla", "funda"]
MIN_PER_KEYWORD = 15


def _ensure_scenario_products(prods, annotated, extra, rng):
    from .textutils import normalize
    titles = prods["product_title"].fillna("").map(normalize)
    current = set(annotated) | set(extra)
    protected, add = set(), []
    for kw in SCENARIO_KEYWORDS:
        has = titles[titles.str.contains(kw, regex=False)]
        inside = [p for p in has.index if p in current]
        protected.update(inside)
        need = MIN_PER_KEYWORD - len(inside)
        if need > 0:
            outside = [p for p in has.index if p not in current]
            if outside:
                pick = rng.choice(outside, size=min(need, len(outside)), replace=False)
                add.extend(pick); current.update(pick); protected.update(pick)
    # Se eliminan tantos distractores no protegidos como productos añadidos (tamaño constante)
    removable = [p for p in extra if p not in protected]
    drop = set(rng.choice(removable, size=min(len(add), len(removable)), replace=False)) if add else set()
    out = [p for p in extra if p not in drop] + list(add)
    print(f"Productos añadidos para escenarios: {len(add)}")
    return np.array(out, dtype=object)


def prepare_data(force=False):
    """Genera catalog.parquet, queries.parquet y qrels.parquet en DATA_DIR."""
    C.ensure_dirs()
    out_cat = C.DATA_DIR / "catalog.parquet"
    if out_cat.exists() and not force:
        print("Datos ya preparados; use force=True para regenerarlos.")
        return load_prepared()

    rng = np.random.default_rng(C.SEED)
    ex = load_examples()
    print(f"Ejemplos ES (versión reducida): {len(ex):,} pares, {ex.query_id.nunique():,} consultas")

    dev = _select_queries(ex, "train", C.N_DEV_QUERIES, rng)
    dev["split"] = "dev"
    test = _select_queries(ex, "test", C.N_TEST_QUERIES, rng)
    test["split"] = "test"
    queries = pd.concat([dev, test], ignore_index=True)

    qrels = ex[ex["query_id"].isin(queries["query_id"])][["query_id", "product_id", "esci_label"]].copy()
    qrels["gain"] = qrels["esci_label"].map(C.ESCI_GAINS)

    prods = load_products_es()
    prods = prods.drop_duplicates("product_id").set_index("product_id")

    # Descarta consultas con algún producto anotado sin ficha (para que TODOS sus candidatos estén en el catálogo)
    missing = set(qrels["product_id"]) - set(prods.index)
    if missing:
        bad_q = set(qrels[qrels["product_id"].isin(missing)]["query_id"])
        print(f"Se descartan {len(bad_q)} consultas con productos sin ficha")
        queries = queries[~queries["query_id"].isin(bad_q)]
        qrels = qrels[~qrels["query_id"].isin(bad_q)]

    annotated = pd.unique(qrels["product_id"])
    if len(annotated) > C.CATALOG_SIZE:
        raise ValueError("CATALOG_SIZE menor que el número de productos anotados")

    # Distractores: productos ES anotados para OTRAS consultas (fichas reales y variadas)
    pool = np.setdiff1d(pd.unique(ex["product_id"]), annotated)
    pool = np.intersect1d(pool, prods.index.values)
    n_extra = C.CATALOG_SIZE - len(annotated)
    extra = rng.choice(pool, size=min(n_extra, len(pool)), replace=False)
    extra = _ensure_scenario_products(prods, annotated, extra, rng)
    ids = np.concatenate([annotated, extra])

    cat = prods.loc[ids].reset_index()
    cat = pd.DataFrame({
        "product_id": cat["product_id"],
        "title": cat["product_title"].fillna("").map(strip_html),
        "description": cat["product_description"].fillna("").map(strip_html),
        "bullets": cat["product_bullet_point"].fillna("").map(strip_html),
        "brand": cat["product_brand"].fillna("").map(strip_html),
        "color": cat["product_color"].fillna("").map(strip_html),
    })
    cat["passage"] = cat.apply(build_passage, axis=1)
    cat = cat.sort_values("product_id").reset_index(drop=True)

    cat.to_parquet(out_cat, index=False)
    queries.to_parquet(C.DATA_DIR / "queries.parquet", index=False)
    qrels.to_parquet(C.DATA_DIR / "qrels.parquet", index=False)

    summary = {
        "catalog_products": int(len(cat)),
        "annotated_products": int(len(annotated)),
        "distractors": int(len(extra)),
        "dev_queries": int((queries.split == "dev").sum()),
        "test_queries": int((queries.split == "test").sum()),
        "judgements": int(len(qrels)),
        "label_distribution": qrels["esci_label"].value_counts().to_dict(),
        "seed": C.SEED,
    }
    (C.DATA_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return cat, queries, qrels


def load_prepared():
    cat = pd.read_parquet(C.DATA_DIR / "catalog.parquet")
    queries = pd.read_parquet(C.DATA_DIR / "queries.parquet")
    qrels = pd.read_parquet(C.DATA_DIR / "qrels.parquet")
    return cat, queries, qrels
