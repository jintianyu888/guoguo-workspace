#!/usr/bin/env bash
# usage-report.sh v1 —— 只读汇报：读 state/usage/<date>.json，不采集、不碰审批
# 2026-11-21 果果落地（根因：model 身份 exec=mode ask，采集脚本在 cron 里挂审批 30 分钟）
# 采集已搬出 agent → systemd timer oc-usage-snapshot.timer（每日 21:20）
# 用法: bash tools/usage-report.sh [YYYY-MM-DD]   rc=0 恒成功（缺失照实报，不装红）
set -u
W=/home/j/.openclaw/workspace
D=${1:-$(date +%F)}
F=$W/state/usage/$D.json
if [ ! -f "$F" ]; then
  echo "用量快照 $D 缺失；采集由 oc-usage-snapshot.timer（21:20）负责"
  echo "最近一份：$(ls -1 $W/state/usage/*.json 2>/dev/null | tail -1 | xargs -r basename)"
  exit 0
fi
python3 "$W/tools/usage-report-parse.py" "$F"
exit 0
