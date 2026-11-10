#!/usr/bin/env bash
# maintenance.sh — 维护窗口开关（2026-11-07 主公令：维护期间的告警不该推给主公）
# 用法: maintenance.sh start <分钟> [原因] | stop | status
set -u
W=/home/j/.openclaw/workspace
FLAG=$W/state/work/.maintenance
PAUSE=$W/state/work/.watchdog-pause
LOG=$W/state/maintenance.log
cmd="${1:-status}"
case "$cmd" in
  start)
    mins="${2:-15}"; reason="${3:-未标注}"
    until=$(( $(date +%s) + mins*60 ))
    echo "$until $reason" > "$FLAG"
    touch "$PAUSE"
    echo "$(date '+%F %T') START ${mins}min until=$(date -d @$until '+%F %T') reason=$reason writer=maintenance.sh" >> "$LOG"
    echo "维护窗口已开启：${mins} 分钟（至 $(date -d @$until '+%H:%M')），原因：$reason" ;;
  stop)
    rm -f "$FLAG" "$PAUSE"
    echo "$(date '+%F %T') STOP writer=maintenance.sh" >> "$LOG"
    echo "维护窗口已关闭" ;;
  status)
    if [ -f "$FLAG" ]; then
      u=$(awk '{print $1}' "$FLAG"); r=$(cut -d' ' -f2- "$FLAG")
      if [ "$(date +%s)" -lt "$u" ]; then
        echo "维护中：至 $(date -d @$u '+%F %T')，原因：$r"
      else
        echo "维护标记已过期（$r），可 stop 清理"
      fi
    else
      echo "非维护状态"
    fi ;;
  *) echo "用法: maintenance.sh start <分钟> [原因] | stop | status"; exit 64 ;;
esac