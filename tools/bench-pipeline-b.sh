#!/bin/bash
# B 机模型评测流水线：逐个下载 → 实测 → 落台账（2026-10-30 主公令：都试，数据留下）
cd /home/j/.openclaw/workspace
LOG=state/work/bench-pipeline.log
MODELS="qwen3.5:9b devstral-small-2:24b qwen3.5:27b qwen3-coder:30b"

have() { curl -s --max-time 10 http://127.0.0.1:11434/api/tags | grep -q "\"$1\""; }

echo "=== 流水线启动 $(date +%F' '%T) ===" >> "$LOG"
for m in $MODELS; do
  nm=$(echo "$m" | tr '/' '_')
  if have "$m"; then
    echo "[$(date +%T)] $m 已存在，直接实测" >> "$LOG"
  else
    echo "[$(date +%T)] 开始下载 $m" >> "$LOG"
    curl -sN --max-time 7200 -X POST http://127.0.0.1:11434/api/pull \
      -d "{\"model\":\"$m\",\"stream\":true}" > "state/work/pull-$nm.log" 2>&1
    rc=$?
    echo "[$(date +%T)] $m 下载结束 rc=$rc" >> "$LOG"
    if [ $rc -ne 0 ] || ! have "$m"; then
      echo "[$(date +%T)] $m 下载失败，跳过实测" >> "$LOG"
      continue
    fi
  fi
  echo "[$(date +%T)] 实测 $m" >> "$LOG"
  timeout 1800 python3 tools/bench-suite-b.py "$m" >> "$LOG" 2>&1
  echo "[$(date +%T)] $m 实测完成" >> "$LOG"
done
echo "=== 流水线结束 $(date +%F' '%T) ===" >> "$LOG"
timeout 60 bash tools/notify.sh "B机模型评测完成，台账 state/work/model-bench-b.md" || true
