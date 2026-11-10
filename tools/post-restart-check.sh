#!/bin/bash
# post-restart-check.sh — 重启后核验并报平安（一次性任务调用）
set -u
WS=/home/j/.openclaw/workspace
OUT=$WS/state/work/post-restart-report.txt
{
  echo "时间: $(date '+%F %H:%M:%S')"
  systemctl --user show openclaw-gateway -p ActiveState -p ExecMainStartTimestamp -p MemoryCurrent 2>/dev/null
  echo "PID: $(pgrep -f 'openclaw.*gateway' | head -1)"
  echo "版本: $(openclaw --version 2>&1 | tail -1)"
  echo "端口18789: $(ss -ltn 2>/dev/null | grep -c 18789)"
  echo "扩展通道: $(timeout 30 openclaw browser status --browser-profile chrome 2>/dev/null | grep -E '^running:' | head -1)"
} > "$OUT" 2>&1
BAL=$(timeout 25 sh $WS/tools/ds-balance.sh 2>/dev/null | tail -1)
[ -z "$BAL" ] && BAL="未采集"
PID=$(pgrep -f 'openclaw.*gateway' | head -1)
RSS="?"
[ -n "$PID" ] && RSS=$(awk '/VmRSS/{print int($2/1024)"MB"}' /proc/$PID/status 2>/dev/null)
bash $WS/tools/notify.sh "✅ 重启完成核验：
$(cat $OUT)
余额: $BAL
RSS: $RSS" >/dev/null 2>&1
