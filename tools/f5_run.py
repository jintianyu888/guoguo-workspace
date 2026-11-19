#!/usr/bin/env python3
"""f5_run.py — 绕开 torchcodec，用 soundfile 读音频跑 F5-TTS CLI"""
import sys, numpy as np, torch, soundfile as sf, torchaudio

def _load(path, **kw):
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return torch.from_numpy(data.T.copy()), sr

torchaudio.load = _load

from f5_tts.infer.infer_cli import main  # noqa: E402

if __name__ == "__main__":
    sys.argv[0] = "f5-tts_infer-cli"
    main()
