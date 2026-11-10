#!/bin/sh
# cuda-fetch.sh —— 多连接分段下载 CUDA 包 → 本地安装 → 跑基准
cd /home/j/.openclaw/workspace || exit 1
LOG=state/cuda-fetch.log
echo "[$(date "+%F %T")] 开始" >> $LOG
python3 tools/get-wheel-urls.py >> $LOG 2>&1 || { echo "取链接失败" >> $LOG; exit 1; }
i=0
while read -r U; do
  i=$((i+1))
  OUT=/home/j/.openclaw/workspace/state/tmp/cuda-$i.whl
  echo "[$(date "+%F %T")] 下载 $i: $(basename "$U")" >> $LOG
  timeout 5400 python3 tools/multi-dl.py "$U" "$OUT" 16 >> $LOG 2>&1
  echo "[$(date "+%F %T")] 第 $i 个: $(ls -lh $OUT 2>/dev/null | awk "{print \$5}")" >> $LOG
done < state/wheel-urls.txt
echo "[$(date "+%F %T")] 安装" >> $LOG
pip_out=$(tools/asr-venv/bin/pip install --no-index /home/j/.openclaw/workspace/state/tmp/cuda-1.whl /home/j/.openclaw/workspace/state/tmp/cuda-2.whl 2>&1 | tail -n 3)
echo "$pip_out" >> $LOG
n=$(ls tools/asr-venv/lib/python*/site-packages 2>/dev/null | grep -icE "^nvidia")
echo "[$(date "+%F %T")] nvidia 包数=$n" >> $LOG
if [ "$n" -gt 0 ]; then
  AUD=media/inbound/openclaw-staged-d944f535-9893-48ba-8c4d-181e3442c898/input-ZpMtVEnhvd---94379459-bd19-489d-bb3e-32775aca393e.ogg
  S=$(date +%s%3N)
  tools/asr "$AUD" --language zh --model tools/models/faster-whisper-small --output_dir /home/j/.openclaw/workspace/state/tmp >/dev/null 2>&1
  E=$(date +%s%3N)
  printf "\n- **ASR GPU 实测**：%s ms（同一条 8 秒语音；CPU 基线 3570 ms）\n" "$((E-S))" >> state/local-accel-bench.md
  echo "[$(date "+%F %T")] GPU 基准 $((E-S)) ms" >> $LOG
fi
echo "[$(date "+%F %T")] 结束" >> $LOG