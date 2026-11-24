#!/usr/bin/env bash
# r39-jump-upgrade.sh —— R39 升级允许跨版本直跳（2026-11-24 主公令）
set -u
W=/home/j/.openclaw/workspace
fail=0
grep -q '允许跨版本直跳' "$W/docs/升级规则-20261121.md" || { echo "RED 文档缺少「允许跨版本直跳」条款"; fail=1; }
grep -q 'date +%u' "$W/tools/restart-window.sh" || { echo "RED restart-window.sh 缺工作日闸门"; fail=1; }
grep -q 'UPGRADE_MIN_DAYS' "$W/tools/upgrade-decide.py" && { echo "RED upgrade-decide.py 仍有成熟度门槛"; fail=1; }
[ "$fail" = 0 ] && echo "GREEN R39 允许跨版本直跳、工作日闸门在、无成熟度门槛"
exit $fail
