#!/bin/sh
# cudnn-fetch.sh —— 多连接下载 cuDNN（正确文件名）→ 安装 → 跑 GPU 基准
cd /home/j/.openclaw/workspace || exit 1
LOG=state/cudnn-fetch.log
echo "[$(date "+%F %T")] 开始" >> $LOG
URL=$(python3 - <<PY 2>>$LOG
import json, urllib.request
d = json.load(urllib.request.urlopen("https://pypi.org/pypi/nvidia-cudnn-cu12/json", timeout=25))
c = [f["url"] for f in d["urls"] if f["filename"].endswith(".whl") and "manylinux" in f["filename"] and "x86_64" in f["filename"]]
print(c[0])
PY
)
[ -n "$URL" ] || { echo "取链接失败" >> $LOG; exit 1; }
NAME=$(basename "$URL")
echo "[$(date "+%F %T")] 下载 $NAME" >> $LOG
mkdir -p state/dl
timeout 5400 python3 tools/multi-dl.py "$URL" "state/dl/$NAME" 16 >> $LOG 2>&1
echo "[$(date "+%F %T")] 完成 $(ls -lh state/dl/$NAME 2>/dev/null | awk "{print \$5}")" >> $LOG
tools/asr-venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "state/dl/$NAME" >> $LOG 2>&1
n=$(ls tools/asr-venv/lib/python*/site-packages 2>/dev/null | grep -icE "^nvidia")
echo "[$(date "+%F %T")] nvidia 包数=$n" >> $LOG
if [ "$n" -gt 0 ]; then
  AUD=media/inbound/openclaw-staged-d944f535-9893-48ba-8c4d-181e3442c898/input-ZpMtVEnhvd---94379459-bd19-489d-bb3e-32775aca393e.ogg
  S=$(date +%s%3N)
  tools/asr "$AUD" --language zh --model tools/models/faster-whisper-small --output_dir /tmp >/dev/null 2>&1
  E=$(date +%s%3N)
  printf "\n- **ASR GPU 实测**：%s ms（同一条 8 秒语音；CPU 基线 3570 ms）\n" "$((E-S))" >> state/local-accel-bench.md
  echo "[$(date "+%F %T")] GPU 基准 $((E-S)) ms" >> $LOG
fi
echo "[$(date "+%F %T")] 结束" >> $LOG