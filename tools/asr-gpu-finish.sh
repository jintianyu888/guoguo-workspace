#!/bin/sh
# asr-gpu-finish.sh v2 —— 等 CUDA 依赖装完 → 跑 GPU 基准 → 记录结果
WS=/home/j/.openclaw/workspace
LOG="$WS/state/asr-gpu-finish.log"
BENCH="$WS/state/local-accel-bench.md"
AUD="$WS/media/inbound/openclaw-staged-d944f535-9893-48ba-8c4d-181e3442c898/input-ZpMtVEnhvd---94379459-bd19-489d-bb3e-32775aca393e.ogg"
echo "[$(date "+%F %T")] v2 启动：等 pip 真正结束（每 60s 查一次，最多 6 小时）" >> "$LOG"
i=0
while [ $i -lt 360 ]; do
  pgrep -f "tools/asr-venv/bin/pip" >/dev/null 2>&1 || break
  i=$((i+1)); sleep 60
done
n=$(ls $WS/tools/asr-venv/lib/python*/site-packages 2>/dev/null | grep -icE "^nvidia")
echo "[$(date "+%F %T")] pip 结束，nvidia 包数=$n" >> "$LOG"
if [ "$n" -gt 0 ] && [ -f "$AUD" ]; then
  cd "$WS" || exit 0
  S=$(date +%s%3N)
  tools/asr "$AUD" --language zh --model tools/models/faster-whisper-small --output_dir /tmp >/dev/null 2>&1
  E=$(date +%s%3N)
  echo "[$(date "+%F %T")] ASR_GPU_ms=$((E-S))" >> "$LOG"
  printf "\n- **ASR GPU 实测**：%s ms（同一条 8 秒语音；CPU 基线 3570 ms）\n" "$((E-S))" >> "$BENCH"
else
  echo "[$(date "+%F %T")] 依赖未装成（n=$n）" >> "$LOG"
fi
echo "[$(date "+%F %T")] 收尾结束" >> "$LOG"