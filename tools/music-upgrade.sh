#!/bin/bash
# 作曲管家升级：独立 venv(demucs) + 下载 musicgen-melody/large + 自检
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
V=/home/j/.openclaw/venvs/demucs
LOG=/home/j/.openclaw/workspace/state/music-upgrade-status.txt
exec > >(tee -a /home/j/.openclaw/workspace/state/tmp/music-upgrade.log) 2>&1
echo "=== START $(date) ==="
"$V/bin/pip" install -i https://pypi.tuna.tsinghua.edu.cn/simple librosa demucs
echo "PIP_RC=$?"
export HF_ENDPOINT=https://hf-mirror.com
/home/j/.openclaw/venvs/tts312/bin/python - <<'PY'
from transformers import MusicgenForConditionalGeneration as M
for n in ("facebook/musicgen-melody","facebook/musicgen-large"):
    try: M.from_pretrained(n); print("OK",n,flush=True)
    except Exception as e: print("FAIL",n,repr(e)[:150],flush=True)
PY
echo "DL_RC=$?"
echo "demo: librosa import -> $("$V/bin/python" -c 'import librosa;print("OK")' 2>&1 | tail -1)"
{ echo "音乐升级自检 $(date)"; echo "venv librosa/demucs: $("$V/bin/python" -c 'import librosa,demucs;print("OK")' 2>&1|tail -1)"; echo "large: $(du -sh /home/j/.cache/huggingface/hub/models--facebook--musicgen-large 2>/dev/null|cut -f1)"; echo "melody: $(du -sh /home/j/.cache/huggingface/hub/models--facebook--musicgen-melody 2>/dev/null|cut -f1)"; } > "$LOG"
echo "=== DONE $(date) ==="
