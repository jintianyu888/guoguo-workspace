#!/bin/bash
# reentry-watch.sh —— 盯 11.10 的 plugin load reentry / agent 准入失败（零 token）
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
set -uo pipefail
W=/home/j/.openclaw/workspace
TREND="$W/state/work/reentry-trend.jsonl"
COOL="$W/state/work/.reentry-alert-ts"
RE=$(journalctl --user -u openclaw-gateway --since "60 min ago" --no-pager 2>/dev/null | grep -c "plugin load reentry")
SU=$(journalctl --user -u openclaw-gateway --since "60 min ago" --no-pager 2>/dev/null | grep -c "Sessions remain unavailable")
VER=$(openclaw --version 2>/dev/null | grep -oE '[0-9]{4}\.[0-9]+\.[0-9]+' | head -1)
TS=$(date '+%F %T')
echo "{\"ts\":\"$TS\",\"ver\":\"$VER\",\"reentry\":$RE,\"sessions_unavailable\":$SU}" >> "$TREND"
tail -n 2000 "$TREND" > "$TREND.tmp" && mv "$TREND.tmp" "$TREND"

ALERT=0
[ "$RE" -ge 50 ] && ALERT=1
[ "$SU" -ge 1 ] && ALERT=1
if [ "$ALERT" = "1" ]; then
  NOW=$(date +%s)
  LAST=$(cat "$COOL" 2>/dev/null || echo 0)
  if [ $((NOW - LAST)) -ge 3600 ]; then
    echo "$NOW" > "$COOL"
    timeout 60 bash "$W/tools/notify.sh" "【网关异常·11.10】近60分钟 plugin load reentry=$RE、Sessions unavailable=$SU（版本 $VER）。已知缺陷，处置见 state/work/reentry-trend.jsonl" >/dev/null 2>&1 || true
    echo "[$TS] ALERT reentry=$RE su=$SU" >> "$W/state/work/reentry-watch.log"
  fi
fi
echo "[$TS] reentry=$RE su=$SU ver=$VER"
