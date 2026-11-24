"""Integración extremo a extremo: audio -> ASR -> agente (RAG + herramientas) -> TTS -> audio.

También centraliza la carga de modelos y el registro de memoria GPU / tiempos de carga
(la carga inicial se separa de la latencia de las consultas posteriores).
"""
import gc
import re
import time
from pathlib import Path

import torch

from . import config as C


def gpu_mem():
    if not torch.cuda.is_available():
        return {}
    return {"allocated_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "reserved_gb": round(torch.cuda.memory_reserved() / 1e9, 2),
            "max_allocated_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2)}


def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class ModelRegistry:
    """Carga perezosa de modelos con registro de tiempo de carga y memoria incremental."""

    def __init__(self):
        self.models, self.load_report = {}, []

    def load(self, name, factory):
        if name in self.models:
            return self.models[name]
        free_memory()
        before = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        t0 = time.perf_counter()
        m = factory()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        dt = time.perf_counter() - t0
        after = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        self.models[name] = m
        self.load_report.append({"modelo": name, "carga_s": round(dt, 1),
                                 "vram_gb": round((after - before) / 1e9, 2), **gpu_mem()})
        print(f"✔ {name}: {dt:.1f} s, +{(after - before) / 1e9:.2f} GB VRAM")
        return m

    def unload(self, name):
        if name in self.models:
            del self.models[name]
            free_memory()


class VoiceAssistant:
    def __init__(self, asr, agent, tts=None, audio_dir=C.AUDIO_DIR):
        self.asr, self.agent, self.tts = asr, agent, tts
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def turn(self, wav_path, t_end=None, correction=None, perturb=None, tag="turn", play=False, asr_result=None):
        """Procesa un turno hablado.

        t_end: instante (perf_counter) en que terminó la grabación; si no se da, se usa el actual.
        correction: texto corregido por el usuario tras revisar la transcripción (se ejecuta
                    ESTE texto, nunca el erróneo).
        perturb: (patrón, reemplazo) para simular un error de ASR reproducible (escenario S06).
        asr_result: (texto, segundos) si la transcripción ya se hizo para que el usuario la revisara;
                    el tiempo de revisión humana NO se cuenta como latencia del sistema.
        """
        if asr_result is not None:
            asr_text, asr_s = asr_result
            t0 = time.perf_counter() - asr_s
        else:
            t0 = t_end or time.perf_counter()
            asr_text, asr_s = self.asr.transcribe(wav_path)
        raw_asr = asr_text
        if perturb:
            asr_text = re.sub(perturb[0], perturb[1], asr_text, flags=re.I)
        used = correction if correction else asr_text
        r = self.agent.handle(used)
        tts_s, out_wav = 0.0, None
        if self.tts is not None:
            out_wav = self.audio_dir / f"{tag}_respuesta.wav"
            _, tts_s = self.tts.synthesize(r["tts_text"], out_wav)
        total = time.perf_counter() - t0
        # Devuelve al driver la caché de bloques libres: con LLM + ASR + TTS en la misma GPU, la caché
        # del asignador crece hasta desbordar la VRAM (en Windows el driver pagina a RAM y todo se ralentiza)
        free_memory()
        r["gpu"] = gpu_mem()
        r.update({"audio_in": str(wav_path), "audio_out": str(out_wav) if out_wav else None,
                  "asr_raw": raw_asr, "asr_text": asr_text, "corrected": bool(correction), "executed_text": used,
                  "latency": {"asr_s": asr_s, "agente_llm_s": r["timing"]["llm_s"],
                              "agente_herramientas_s": r["timing"]["tools_s"],
                              "agente_total_s": r["timing"]["agent_total_s"], "tts_s": tts_s,
                              "total_s": total}})
        if play and out_wav:
            from IPython.display import Audio, display
            display(Audio(str(out_wav), autoplay=True))
        return r
