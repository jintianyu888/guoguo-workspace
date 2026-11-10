#!/usr/bin/env bash
# b-return-watch.sh — 等 B 机(192.168.1.107)恢复，记录首次可达时间（2026-11-07 21:18 因 B 整机掉线）
set -u
OUT=/home/j/.openclaw/workspace/state/work/b-returned.txt
for i in $(seq 1 360); do   # 最多 6 小时
  if ping -c 1 -W 2 192.168.1.107 >/dev/null 2>&1; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://192.168.1.107:11434/api/version 2>/dev/null)
    echo "首次可达 $(date '+%F %T')  ollama_http=$code  等待轮次=$i" >> "$OUT"
    if [ "$code" = "200" ]; then exit 0; fi
  fi
  sleep 60
done
echo "6 小时仍未恢复 $(date '+%F %T')" >> "$OUT"
