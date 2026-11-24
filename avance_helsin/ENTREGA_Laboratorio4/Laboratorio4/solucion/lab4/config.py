"""Configuración central del Laboratorio 4 (asistente de compras por voz).

Todos los parámetros que afectan a la reproducibilidad (semillas, tamaños de
muestra, modelos) se definen aquí para que el notebook y los scripts usen
exactamente los mismos valores.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
# En Colab se recomienda montar Drive y usar /content/drive/MyDrive/lab4_dl
# para conservar audios, índices y resultados entre sesiones.
BASE_DIR = Path(os.environ.get("LAB4_BASE", "/content/lab4_work"))
RAW_DIR = BASE_DIR / "raw"            # parquet originales de ESCI
DATA_DIR = BASE_DIR / "data"          # catálogo, consultas, qrels
INDEX_DIR = BASE_DIR / "index"        # embeddings y BM25
# La base SQLite va en disco local (no en Drive: el FUSE de Drive es lento y no soporta bien
# los bloqueos de SQLite). Es regenerable de forma determinista con la semilla.
STORE_DIR = Path(os.environ.get("LAB4_STORE", "/content/lab4_store"))
AUDIO_DIR = BASE_DIR / "audios"       # grabaciones de usuario y respuestas TTS
RESULTS_DIR = BASE_DIR / "results"    # métricas, logs, gráficos

ESCI_URL = "https://github.com/amazon-science/esci-data/raw/main/shopping_queries_dataset/"
ESCI_FILES = [
    "shopping_queries_dataset_examples.parquet",
    "shopping_queries_dataset_products.parquet",
    "shopping_queries_dataset_sources.csv",
]

# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
SEED = 2026
LOCALE = "es"
N_DEV_QUERIES = 150         # consultas de split=train (desarrollo / ajuste)
N_TEST_QUERIES = 250        # consultas de split=test (evaluación, nunca se ajusta con ellas)
CATALOG_SIZE = 15000        # >= 5000; productos anotados + distractores del mismo locale
MIN_JUDGEMENTS = 8          # consultas con al menos este número de candidatos anotados

# Ganancias pedidas por el enunciado para nDCG@10
ESCI_GAINS = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}

# ---------------------------------------------------------------------------
# Modelos (todos se ejecutan localmente en la GPU de Colab, sin APIs externas)
# ---------------------------------------------------------------------------
@dataclass
class ModelConfig:
    asr: str = "openai/whisper-large-v3-turbo"          # 809M, fp16 ~1.6 GB
    embedder: str = "intfloat/multilingual-e5-base"     # 278M, fp16 ~0.6 GB
    reranker: str = "BAAI/bge-reranker-v2-m3"           # 568M, fp16 ~1.1 GB
    llm: str = "Qwen/Qwen3-8B"                          # 8B en 4 bits NF4 ~5.9 GB
    llm_fallback: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_4bit: bool = True
    tts: str = "tts_models/multilingual/multi-dataset/xtts_v2"  # ~1.9 GB
    speaker_verif: str = "microsoft/wavlm-base-plus-sv"  # similitud de voz
    max_new_tokens: int = 384
    # Prefill por bloques: sin él, la memoria transitoria del LLM crece de forma cuadrática con el prompt
    # (5,7 GiB con 4 150 tokens) y la etapa de voz no cabe en la T4; con bloques de 1 024 tokens baja a 0,8 GiB
    # sin cambiar las respuestas (medido en una T4 simulada con tope de 14,4 GiB). 0 = desactivado.
    prefill_chunk_size: int = 1024


@dataclass
class RetrievalConfig:
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    rrf_k: int = 60
    w_bm25: float = 1.0          # peso del ranking léxico en RRF (se ajusta en dev)
    w_dense: float = 1.0         # peso del ranking denso en RRF (se ajusta en dev)
    rerank_depth: int = 30       # candidatos que pasan al cross-encoder
    max_passage_chars: int = 1200
    use_reranker: bool = True
    use_bm25: bool = True
    use_dense: bool = True


@dataclass
class AgentConfig:
    max_steps: int = 6            # llamadas a herramientas por turno de usuario
    history_turns: int = 6        # turnos de diálogo que se pasan literalmente al LLM
    search_k: int = 5
    currency: str = "EUR"
    tax_rate: float = 0.21        # IVA España
    shipping_flat: float = 4.99
    free_shipping_from: float = 50.0
    max_qty_per_item: int = 20
    use_rules: bool = True        # reglas deterministas de memoria y control (False = ablación)


MODELS = ModelConfig()
RETRIEVAL = RetrievalConfig()
AGENT = AgentConfig()


def ensure_dirs():
    for d in [RAW_DIR, DATA_DIR, INDEX_DIR, STORE_DIR, AUDIO_DIR, RESULTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
