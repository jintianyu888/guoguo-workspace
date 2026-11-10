#!/usr/bin/env python3
"""tts_gpu.py —— 本地 GPU 中文语音合成（Kokoro-82M，离线、零 token、走 CUDA）。
用法: tts_gpu.py "文字" out.wav [voice]
voice 默认 zf_xiaoxiao；可选 zf_xiaobei/zf_xiaoni/zf_xiaoxiao/zf_xiaoyi/
zm_yunjian/zm_yunxi/zm_yunxia/zm_yunyang
"""
import os, sys
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import numpy as np
import soundfile as sf
from kokoro import KPipeline


def main():
    if len(sys.argv) < 3:
        print('用法: tts_gpu.py "文字" out.wav [voice]', file=sys.stderr)
        sys.exit(2)
    text, out = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "zf_xiaoxiao"
    pipe = KPipeline(lang_code="z")
    chunks = [a for _, _, a in pipe(text, voice=voice)]
    audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
    sf.write(out, audio, 24000)
    print(f"wrote {out} {len(audio)/24000:.2f}s voice={voice}")


if __name__ == "__main__":
    main()
