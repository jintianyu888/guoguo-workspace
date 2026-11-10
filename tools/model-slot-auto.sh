#!/bin/bash
# model-slot-auto.sh —— 合并版时段切换（2026-10-23 双审通过，替代 4 条独立 cron）
# 09→peak(GLM) 12→offpeak(DeepSeek) 14→afternoon(Kimi) 18→offpeak(DeepSeek)
h=$(date +%H)
case "$h" in
  09) s=peak ;;
  12) s=offpeak ;;
  14) s=afternoon ;;
  18) s=offpeak ;;
  *)  s=offpeak ;;
esac
echo "[$(date '+%F %T')] auto-slot hour=$h → $s"
exec bash /home/j/.openclaw/workspace/tools/model-slot.sh "$s"

