#!/bin/bash
# 周/月复盘推送：--weekly 或 --monthly
set -u
cd /home/j/.openclaw/workspace || exit 1
MODE="${1:---weekly}"
OUT=$(timeout 120 python3 tools/plan-retro.py $MODE 2>&1)
RC=$?
PROG=$(timeout 60 python3 tools/plan-report.py --level all 2>&1 | head -4)
timeout 60 bash tools/notify.sh "$(printf "%s\n\n%s" "$PROG" "$OUT")" >/dev/null 2>&1 || true
echo "$OUT"
[ $RC -ne 0 ] && echo "RETRO_RC=$RC（未兑现>3，需拆分/砍单）"
exit 0
