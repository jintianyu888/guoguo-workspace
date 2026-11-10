#!/bin/bash
# 盯 B 机 gpt-oss:20b 装完就自动实测（2026-10-29 主公令）
cd /home/j/.openclaw/workspace
OUT=/home/j/.openclaw/workspace/state/work/bench-b.txt
for i in $(seq 1 480); do
  if curl -s --max-time 8 http://127.0.0.1:11434/api/tags 2>/dev/null | grep -q "gpt-oss:20b"; then
    echo "发现 gpt-oss:20b，开始实测 $(date +%T)" >> "$OUT"
    timeout 900 python3 tools/bench-remote-llm.py gpt-oss:20b >> "$OUT" 2>&1
    R=$(grep -o "[0-9.]* tok/s" "$OUT" | head -1)
    timeout 60 bash tools/notify.sh "B 机 gpt-oss:20b 装完并实测：${R:-未测出}，详情 state/work/bench-b.txt" || true
    exit 0
  fi
  sleep 30
done
echo "4 小时未见 gpt-oss:20b" >> "$OUT"