#!/bin/bash
# printer-watch.sh — 打印机开印前/每小时自检 v1.0（零 token，systemd 定时）
# 逻辑：printer-status.py --json → 有异常且异常集合与上次不同才推「果果警告」，避免每小时重复刷屏
set -uo pipefail
WS=/home/j/.openclaw/workspace
ST="$WS/state/work/printer-watch.state"
JSON=$(timeout 25 python3 "$WS/tools/printer-status.py" --json 2>/dev/null); rc=$?
if [ -z "$JSON" ]; then
  key="unreachable"
else
  key=$(printf '%s' "$JSON" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("|".join(sorted(d.get("problems") or [])) or "ok")' 2>/dev/null)
fi
prev=$(cat "$ST" 2>/dev/null || true)
if [ "$key" != "$prev" ]; then
  if [ "$key" != "ok" ] && [ -n "$key" ]; then
    bash "$WS/tools/notify.sh" --alert "【打印机自检】状态异常：${key//|/ ／ }
详情: python3 tools/printer-status.py   路径: state/work/printer-watch.state
停发建议：处理缺纸/卡纸后本行会自愈" >/dev/null 2>&1 || true
  fi
  printf '%s' "$key" > "$ST"
  echo "$(date '+%F %T') changed -> $key (rc=$rc)"
else
  echo "$(date '+%F %T') unchanged ($key)"
fi
exit 0
