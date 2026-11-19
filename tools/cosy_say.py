#!/usr/bin/env python3
# cosy_say.py — CosyVoice2 命令行合成（克隆 / 指令控制）
import argparse, os, sys, torch, torchaudio
SRC = "/home/j/.local/src/CosyVoice"
sys.path.insert(0, SRC)
import soundfile as _sf
import torchaudio as _ta


_orig_ta_load = _ta.load


def _sf_load(path, *args, **kw):
    if not isinstance(path, (str, bytes)) and not hasattr(path, "__fspath__"):
        return path, kw.get("sr", 16000)
    data, sr = _sf.read(str(path), always_2d=True, dtype="float32")
    return torch.from_numpy(data.T.copy()), sr


_ta.load = _sf_load

from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav

p = argparse.ArgumentParser()
p.add_argument("text")
p.add_argument("--ref", default="/home/j/.config/guoguo/voice-ref/female-ref.wav")
p.add_argument("--ref-text", default="今天天气不错，我们把这一段话当成参考样本，语速放慢一点，声音清楚一点。")
p.add_argument("--instruct", default="")
p.add_argument("--out", default="/tmp/cosy_out.wav")
p.add_argument("--model-dir", default=SRC + "/pretrained_models/CosyVoice2-0.5B")
a = p.parse_args()

cosy = CosyVoice2(a.model_dir, load_jit=False, load_trt=False, fp16=False)
prompt = load_wav(a.ref, 16000)
chunks = []
if a.instruct:
    for i, j in enumerate(cosy.inference_instruct2(a.text, a.instruct, prompt, stream=False)):
        chunks.append(j["tts_speech"])
else:
    for i, j in enumerate(cosy.inference_zero_shot(a.text, a.ref_text, prompt, stream=False)):
        chunks.append(j["tts_speech"])
if not chunks:
    print("NO_AUDIO", file=sys.stderr); sys.exit(1)
wav = torch.cat(chunks, dim=1)
torchaudio.save(a.out, wav, cosy.sample_rate)
print("OK", a.out, round(wav.shape[1] / cosy.sample_rate, 2), "s")
