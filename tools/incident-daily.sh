#!/usr/bin/env bash
# incident-daily.sh —— 每天 06:40 网关重启/崩溃归因自查
set -u
W=/home/j/.openclaw/workspace
OUT=$(python3 "$W/tools/incident-ledger.py" review --hours 24 2>&1)
N=$(printf '%s\n' "$OUT" | head -1 | grep -oE '共 [0-9]+ 次' | grep -oE '[0-9]+' || echo 0)
echo "$OUT" > "$W/state/incidents/last-review.txt"
if [ "${N:-0}" -ge 3 ]; then
  timeout 90 bash "$W/tools/notify.sh" --alert "告警：过去 24h 网关重启/崩溃 ${N} 次。$(printf '%s\n' "$OUT" | sed -n '3,6p' | tr '\n' ' ')" >/dev/null 2>&1 || true
fi
exit 0
