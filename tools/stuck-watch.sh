#!/bin/bash
# stuck-watch.sh —— 每 30 分钟的卡住检测（零 token），有可行动项才推一条
set -u
W=/home/j/.openclaw/workspace
OUT=$(python3 $W/tools/stuck-watch.py 2>&1)
echo "[$(date '+%F %T')] $OUT" >> $W/state/work/stuck-watch.log
# 只有「我这边的过期未做」或「现役管家空转」才通知；纯 owner 待拍板不刷屏
if printf '%s' "$OUT" | grep -qE '🔴|💤'; then
  # 2026-11-08 20:38 修：普通线（maint 账户）20:00/20:20/20:35 连续发送失败，改走告警 webhook 线（实测 rc=0、<1s），
  # 并把内容截断到 900 字，避免超长导致 400。
  MSG="🕒 卡住检测 $(date '+%H:%M')
$(printf '%s' "$OUT" | head -c 900)"
  bash $W/tools/notify.sh --alert "$MSG" >/dev/null 2>&1
fi
