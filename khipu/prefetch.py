"""Descarga en el nodo de login (los nodos de computo no tienen internet): datos ESCI y modelos."""
import os, sys
sys.path.insert(0, os.path.expanduser("~/lab4/Laboratorio4/solucion"))
from lab4 import config as C, data
C.ensure_dirs()
data.download_esci(); print("ESCI ok", flush=True)
from huggingface_hub import snapshot_download
M = C.MODELS
for repo in [M.embedder, M.reranker, M.asr, M.speaker_verif, M.llm]:
    p = snapshot_download(repo, allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "*.jinja", "*.bpe", "*.vocab"])
    print("ok", repo, p, flush=True)
from TTS.utils.manage import ModelManager
print("xtts", ModelManager().download_model(M.tts)[0], flush=True)
print("PREFETCH_OK", flush=True)
