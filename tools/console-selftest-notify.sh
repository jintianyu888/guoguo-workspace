#!/usr/bin/env bash
# 果果助手自检守护：平时静默，仅失败才告警（2026-10-29 主公令：试跑归果果，不劳主公）
set -u
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/console-selftest.log
OUT=$(timeout 600 bash $WS/tools/console-selftest.sh 2>&1); RC=$?
printf "%s\n%s\n\n" "===== $(date "+%F %T") =====" "$OUT" >> "$LOG"
tail -c 200000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
if [ $RC -ne 0 ]; then
  BAD=$(printf "%s" "$OUT" | grep -c "❌" )
  timeout 60 bash $WS/tools/notify.sh --alert "果果助手自检未过：$BAD 项失败，详情 state/work/console-selftest.log" || true
fi
exit $RC