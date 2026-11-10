#!/bin/sh
# cuda-finish-mirror.sh —— 从清华镜像把 cuDNN / torch 下完 → 装 → 跑 ASR GPU 基准
cd /home/j/.openclaw/workspace || exit 1
L=state/cuda-finish.log
echo "[$(date "+%F %T")] 开始" >> $L
python3 tools/pick-mirror-urls.py >> $L 2>&1
for K in cudnn torch; do
  U=$(python3 -c "import json;print(json.load(open('state/mirror-wheel-urls.json')).get('$K',''))")
  [ -n "$U" ] || continue
  N=$(basename "$U")
  echo "[$(date "+%F %T")] 下载 $K -> $N" >> $L
  timeout 1800 python3 tools/multi-dl.py "$U" "state/dl/$N" 16 >> $L 2>&1
  echo "[$(date "+%F %T")] $K 完成 $(ls -lh state/dl/$N 2>/dev/null | awk "{print \$5}")" >> $L
  case "$K" in
    cudnn) tools/asr-venv/bin/pip install -q --no-deps "state/dl/$N" >> $L 2>&1 ;;
  esac
done
n=$(ls tools/asr-venv/lib/python*/site-packages 2>/dev/null | grep -icE "^nvidia")
echo "[$(date "+%F %T")] nvidia 包数=$n" >> $L
if [ "$n" -gt 0 ]; then
  A=media/inbound/openclaw-staged-5957122d-fcb6-4bbd-b975-289e2608d62d/input-bEliZCkEWu---95405f6c-eead-4b58-ad3b-33989e948a2b.ogg
  S=$(date +%s%3N); timeout 200 tools/asr "$A" --language zh --model tools/models/faster-whisper-small --output_dir /home/j/.openclaw/workspace/state/tmp/gpubench2 >/dev/null 2>&1; E=$(date +%s%3N)
  echo "[$(date "+%F %T")] ASR GPU 基准 $((E-S)) ms（CPU 基线 3570ms）" >> $L
  printf "\n- **ASR GPU 实测**：%s ms（同一条 8 秒语音；CPU 基线 3570 ms）\n" "$((E-S))" >> state/local-accel-bench.md
fi
echo "[$(date "+%F %T")] 结束" >> $L