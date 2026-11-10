#!/bin/sh
# asr-gpu-retry.sh —— 后台慢慢试：镜像 + 断点续传，装成即跑基准（不成功就算了，不打扰主公）
WS=/home/j/.openclaw/workspace
LOG=$WS/state/asr-gpu-retry.log
BENCH=$WS/state/local-accel-bench.md
AUD=$WS/media/inbound/openclaw-staged-d944f535-9893-48ba-8c4d-181e3442c898/input-ZpMtVEnhvd---94379459-bd19-489d-bb3e-32775aca393e.ogg
for i in $(seq 1 12); do
  echo "[$(date "+%F %T")] 第 $i 次尝试" >> "$LOG"
  timeout 900 tools/asr-venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --resume-retries 50 --timeout 180 --retries 10 nvidia-cudnn-cu12 nvidia-cublas-cu12 >> "$LOG" 2>&1
  n=$(ls $WS/tools/asr-venv/lib/python*/site-packages 2>/dev/null | grep -icE "^nvidia")
  echo "[$(date "+%F %T")] 结果 nvidia包数=$n" >> "$LOG"
  if [ "$n" -gt 0 ]; then
    cd "$WS" || exit 0
    S=$(date +%s%3N)
    tools/asr "$AUD" --language zh --model tools/models/faster-whisper-small --output_dir /tmp >/dev/null 2>&1
    E=$(date +%s%3N)
    printf "\n- **ASR GPU 实测**：%s ms（同一条 8 秒语音；CPU 基线 3570 ms）\n" "$((E-S))" >> "$BENCH"
    echo "[$(date "+%F %T")] GPU 基准完成: $((E-S)) ms" >> "$LOG"
    exit 0
  fi
  sleep 600
done
echo "[$(date "+%F %T")] 12 次都失败，收工（保持 CPU 路线）" >> "$LOG"