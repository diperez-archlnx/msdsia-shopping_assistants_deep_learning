"""Voz: grabación en Colab, ASR (Whisper), TTS con clonación (XTTS-v2) y evaluación de la voz."""
import base64
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from . import config as C

ASR_SR = 16000


# ---------------------------------------------------------------------------
# Utilidades de audio
# ---------------------------------------------------------------------------
def to_wav16k(src, dst=None):
    """Convierte cualquier formato (webm/ogg/mp3/m4a/wav) a WAV mono 16 kHz con ffmpeg."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_suffix(".16k.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(ASR_SR), str(dst)],
                   check=True)
    return dst


def load_audio(path, sr=ASR_SR):
    wav, file_sr = sf.read(str(path), dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if file_sr != sr:
        import librosa
        wav = librosa.resample(wav, orig_sr=file_sr, target_sr=sr)
    return wav.astype(np.float32)


# ---------------------------------------------------------------------------
# Grabación desde el navegador (Colab)
# ---------------------------------------------------------------------------
RECORD_JS = r"""
async function recordAudio(maxMs, label) {
  const div = document.createElement('div');
  div.style = 'padding:8px;font-family:sans-serif';
  const btn = document.createElement('button');
  btn.textContent = '⏹ Detener grabación';
  btn.style = 'font-size:16px;padding:6px 14px;background:#c62828;color:white;border:none;border-radius:6px';
  const info = document.createElement('span');
  info.textContent = '  🎙️ Grabando: ' + label;
  div.appendChild(btn); div.appendChild(info); document.body.appendChild(div);
  const stream = await navigator.mediaDevices.getUserMedia({audio: true});
  const rec = new MediaRecorder(stream);
  const chunks = [];
  rec.ondataavailable = e => chunks.push(e.data);
  const stopped = new Promise(res => rec.onstop = res);
  rec.start();
  await Promise.race([new Promise(r => btn.onclick = r), new Promise(r => setTimeout(r, maxMs))]);
  rec.stop(); await stopped;
  stream.getTracks().forEach(t => t.stop());
  div.remove();
  const blob = new Blob(chunks, {type: rec.mimeType});
  return await new Promise(res => { const fr = new FileReader(); fr.onloadend = () => res(fr.result); fr.readAsDataURL(blob); });
}
"""


def record(path, max_seconds=30, label=""):
    """Graba desde el micrófono del navegador. Devuelve (ruta_wav16k, instante_fin_grabación)."""
    from google.colab.output import eval_js
    from IPython.display import Javascript, display
    display(Javascript(RECORD_JS))
    data_url = eval_js(f"recordAudio({int(max_seconds * 1000)}, {label!r})")
    t_end = time.perf_counter()          # fin de la grabación (referencia para la latencia)
    raw = base64.b64decode(data_url.split(",", 1)[1])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    webm = path.with_suffix(".webm")
    webm.write_bytes(raw)
    wav = to_wav16k(webm, path.with_suffix(".wav"))
    return wav, t_end


# ---------------------------------------------------------------------------
# ASR
# ---------------------------------------------------------------------------
class ASR:
    """Whisper large-v3-turbo (fp16). Elegido por su WER en español y por ser ~6x más
    rápido que large-v3 al tener solo 4 capas de decodificador."""

    def __init__(self, model_name=C.MODELS.asr):
        from transformers import pipeline
        t0 = time.perf_counter()
        self.pipe = pipeline("automatic-speech-recognition", model=model_name,
                             torch_dtype=torch.float16, device="cuda:0")
        self.load_s = time.perf_counter() - t0

    def transcribe(self, wav):
        if isinstance(wav, (str, Path)):
            wav = load_audio(wav)
        t0 = time.perf_counter()
        # Troceado solo para audios > 30 s (los turnos normales caben en una ventana de Whisper)
        kw = {"chunk_length_s": 30, "batch_size": 4} if len(wav) > 30 * ASR_SR else {}
        out = self.pipe({"raw": wav, "sampling_rate": ASR_SR},
                        generate_kwargs={"language": "spanish", "task": "transcribe"}, **kw)
        return out["text"].strip(), time.perf_counter() - t0


# ---------------------------------------------------------------------------
# TTS con clonación de voz
# ---------------------------------------------------------------------------
class VoiceTTS:
    """XTTS-v2: TTS multilingüe (incluye español) con clonación zero-shot a partir de
    una grabación de referencia de 6-30 s. Los latentes del hablante se calculan una
    sola vez para que cada respuesta posterior solo pague la síntesis."""

    SR = 24000

    def __init__(self, reference_wav, model_name=C.MODELS.tts):
        os.environ.setdefault("COQUI_TOS_AGREED", "1")   # licencia CPML (uso no comercial / académico)
        from TTS.api import TTS
        t0 = time.perf_counter()
        self.api = TTS(model_name).to("cuda")
        self.model = self.api.synthesizer.tts_model
        self.reference_wav = str(reference_wav)
        self.gpt_latent, self.spk_emb = self.model.get_conditioning_latents(audio_path=[self.reference_wav])
        self.load_s = time.perf_counter() - t0

    @staticmethod
    def split_sentences(text, max_chars=200):
        # Unidades: frases; si una frase excede max_chars se parte por comas y, si hace falta,
        # por palabras (nunca se trunca texto).
        units = []
        for s in re.split(r"(?<=[.!?;:])\s+", text):
            if len(s) <= max_chars:
                units.append(s)
                continue
            for piece in re.split(r"(?<=,)\s+", s):
                while len(piece) > max_chars:
                    cut = piece.rfind(" ", 0, max_chars)
                    cut = cut if cut > 0 else max_chars
                    units.append(piece[:cut]); piece = piece[cut:].strip()
                if piece:
                    units.append(piece)
        parts, cur = [], ""
        for s in units:
            if len(cur) + len(s) + 1 <= max_chars:
                cur = (cur + " " + s).strip()
            else:
                if cur:
                    parts.append(cur)
                cur = s
        if cur:
            parts.append(cur)
        return parts

    @torch.inference_mode()
    def synthesize(self, text, out_path=None, temperature=0.65):
        t0 = time.perf_counter()
        chunks = []
        for s in self.split_sentences(text):
            o = self.model.inference(s, "es", self.gpt_latent, self.spk_emb,
                                     temperature=temperature, enable_text_splitting=False)
            chunks.append(np.asarray(o["wav"], dtype=np.float32))
            chunks.append(np.zeros(int(0.15 * self.SR), dtype=np.float32))
        wav = np.concatenate(chunks) if chunks else np.zeros(self.SR // 2, np.float32)
        dt = time.perf_counter() - t0
        if out_path:
            sf.write(str(out_path), wav, self.SR)
        return wav, dt


# ---------------------------------------------------------------------------
# Similitud de hablante (evaluación de la clonación)
# ---------------------------------------------------------------------------
class SpeakerSimilarity:
    """Embeddings x-vector de WavLM-base-plus-sv; coseno > ~0.86 sugiere mismo hablante
    según la tarjeta del modelo. Se reporta además la similitud referencia-vs-referencia
    (dos mitades de la grabación) como cota superior y una voz distinta como cota inferior."""

    def __init__(self, model_name=C.MODELS.speaker_verif):
        from transformers import AutoFeatureExtractor, WavLMForXVector
        self.fe = AutoFeatureExtractor.from_pretrained(model_name)
        self.model = WavLMForXVector.from_pretrained(model_name).to("cuda").eval()

    @torch.inference_mode()
    def embed(self, wav16k):
        inp = self.fe([wav16k], sampling_rate=ASR_SR, return_tensors="pt", padding=True).to("cuda")
        e = self.model(**inp).embeddings
        return torch.nn.functional.normalize(e, dim=-1)[0].cpu().numpy()

    def similarity(self, wav_a, wav_b):
        return float(np.dot(self.embed(wav_a), self.embed(wav_b)))


def text_overlap(a, b, n=3):
    """Proporción de trigramas de ``a`` presentes en ``b`` (para garantizar que los textos
    sintetizados son distintos del texto de la grabación de referencia)."""
    from .textutils import normalize
    ta, tb = normalize(a).split(), normalize(b).split()
    ga = {tuple(ta[i:i + n]) for i in range(len(ta) - n + 1)}
    gb = {tuple(tb[i:i + n]) for i in range(len(tb) - n + 1)}
    return len(ga & gb) / max(1, len(ga))
