#!/bin/bash
# overview-refresh.sh —— 采集六域健康并同步给面板（零 token）
# 同时产出 json（给外部用）和 js（给面板用 <script> 直接引入，绕开 fetch 依赖）
set -u
W=/home/j/.openclaw/workspace
PANEL=/home/j/openclaw-workspaces/work/果果助手/public
timeout 120 python3 "$W/tools/overview-health.py" >/dev/null 2>&1
rc=$?
if [ -s "$W/state/overview/health.json" ]; then
  cp -f "$W/state/overview/health.json" "$PANEL/overview-data.json"
  { printf 'window.__GV='; cat "$W/state/overview/health.json"; printf ';\n'; } > "$PANEL/overview-data.js"
  echo "[$(date '+%F %T')] rc=$rc synced json+js" >> "$W/state/overview/refresh.log"
else
  echo "[$(date '+%F %T')] rc=$rc NO-DATA" >> "$W/state/overview/refresh.log"
fi
