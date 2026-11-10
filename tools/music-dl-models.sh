#!/bin/bash
# 下载缺失的 MusicGen 模型（走 hf-mirror）
export HF_ENDPOINT=https://hf-mirror.com
PY=/home/j/.openclaw/venvs/tts312/bin/python
$PY - <<'PYEOF'
from transformers import MusicgenForConditionalGeneration as M
for name in ("facebook/musicgen-melody","facebook/musicgen-large"):
    try:
        M.from_pretrained(name)
        print("OK", name)
    except Exception as e:
        print("FAIL", name, repr(e)[:200])
PYEOF
echo "DL-DONE"
