#!/bin/bash
# 每日三次排班推送：三数字 + 挤压/卡点体检 + 昨日兑现 + 唯一待拍板 + 时段计划
set -u
WS=/home/j/.openclaw/workspace
cd "$WS" || exit 1
SLOT="${1:-auto}"
PROG=$(timeout 60 python3 tools/plan-report.py --level all 2>&1 | head -6)
ROLL=$(timeout 60 python3 tools/plan-roll.py --report --days 1 2>&1 | head -12)
GUARD=$(timeout 60 python3 tools/plan-guard.py --all 2>&1 | head -18)
PLAN=$(timeout 60 python3 tools/day-plan.py --slot "$SLOT" 2>&1)
timeout 60 python3 tools/plan-roll.py --snapshot >/dev/null 2>&1
[ -z "$PLAN" ] && { echo "day-plan 无输出"; exit 1; }
MSG=$(printf "%s\n\n%s\n\n%s\n\n%s" "$PROG" "$ROLL" "$GUARD" "$PLAN")
timeout 60 bash tools/notify.sh "$MSG" >/dev/null 2>&1 || true
echo "$MSG"

# 2026-10-28 主公令：计划里不许留尾巴（甩给主公的待办/选择），自动扫描
if [ -f "$WS/tools/loose-end-scan.py" ]; then
  python3 "$WS/tools/loose-end-scan.py" "$WS/state/work/day-plan.md" 2>/dev/null | tail -1
fi
