"""LLM local con llamadas a herramientas (formato nativo de Qwen: <tool_call>{json}</tool_call>).

Se carga en 4 bits NF4 (bitsandbytes) para que quepa junto a ASR, embeddings,
re-ranker y TTS en la T4 de 15 GB de Colab. La decodificación es voraz
(do_sample=False) para que los escenarios sean reproducibles.
"""
import json
import re
import time

import torch

from . import config as C

_TOOL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class LocalLLM:
    def __init__(self, model_name=None, load_4bit=C.MODELS.llm_4bit):
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.model_name = model_name or C.MODELS.llm
        t0 = time.perf_counter()
        kw = {"device_map": "cuda:0", "torch_dtype": torch.float16}
        if load_4bit:
            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        self.tok = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **kw).eval()
        self.load_s = time.perf_counter() - t0
        self.is_qwen3 = "qwen3" in self.model_name.lower()
        # Prefill por bloques (config.ModelConfig.prefill_chunk_size): acota la memoria de los prompts largos.
        from transformers import GenerationConfig
        self.prefill_chunk_size = None
        if C.MODELS.prefill_chunk_size and hasattr(GenerationConfig(), "prefill_chunk_size"):
            self.model.generation_config.prefill_chunk_size = C.MODELS.prefill_chunk_size
            self.prefill_chunk_size = C.MODELS.prefill_chunk_size
        elif C.MODELS.prefill_chunk_size:
            print("⚠️ Esta versión de transformers no admite prefill por bloques: en una T4 los prompts "
                  "largos pueden agotar la memoria de la GPU (actualice transformers).")

    def _prompt(self, messages, tools):
        kw = {"tools": tools} if tools else {}
        if self.is_qwen3:
            kw["enable_thinking"] = False   # modo sin razonamiento: menor latencia, salida directa
        return self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, **kw)

    @torch.inference_mode()
    def generate(self, messages, tools=None, max_new_tokens=C.MODELS.max_new_tokens):
        text = self._prompt(messages, tools)
        enc = self.tok(text, return_tensors="pt").to(self.model.device)
        t0 = time.perf_counter()
        out = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                  temperature=None, top_p=None, top_k=None,
                                  pad_token_id=self.tok.eos_token_id)
        gen = out[0, enc["input_ids"].shape[1]:]
        raw = self.tok.decode(gen, skip_special_tokens=True)
        stats = {"prompt_tokens": int(enc["input_ids"].shape[1]), "new_tokens": int(len(gen)),
                 "gen_s": time.perf_counter() - t0}
        return parse_output(raw), stats


def parse_output(raw):
    """Separa texto final y llamadas a herramientas. Tolera JSON algo malformado."""
    raw = _THINK_RE.sub("", raw).strip()
    calls = []
    for m in _TOOL_RE.finditer(raw):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            try:
                obj = json.loads(m.group(1).replace("'", '"'))
            except json.JSONDecodeError:
                continue
        args = obj.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if "name" in obj:
            calls.append({"name": obj["name"], "arguments": args or {}})
    text = _TOOL_RE.sub("", raw).replace("<tool_call>", "").replace("</tool_call>", "").strip()
    return {"text": text, "tool_calls": calls, "raw": raw}
