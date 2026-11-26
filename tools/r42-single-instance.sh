#!/bin/bash
# r42-single-instance.sh —— 网关单实例护栏校验（2026-11-26 事故 S0051）
set -uo pipefail
W=/home/j/.openclaw/workspace
bad=0
grep -q "gw-start-guard.sh" "$W/tools/gateway-watchdog.sh" || { echo "FAIL watchdog 未经 gw-start-guard.sh 拉起网关"; bad=1; }
grep -q "gw-start-guard.sh" "$W/tools/upgrade-openclaw.sh" || { echo "FAIL upgrade-openclaw 回滚启动未经护栏"; bad=1; }
grep -q "db-integrity-gate.sh" "$W/tools/upgrade-openclaw.sh" || { echo "FAIL upgrade-openclaw 缺少升级后库完整性闸门"; bad=1; }
grep -q "db-integrity-gate.sh" "$W/tools/upgrade-panel.sh" || { echo "FAIL upgrade-panel 缺少迁移后库完整性闸门"; bad=1; }
systemctl --user is-active oc-db-integrity.timer >/dev/null 2>&1 || { echo "FAIL 每日 03:30 库巡检定时器未启用"; bad=1; }
[ "$bad" = "0" ] && { echo "GREEN 网关单实例护栏 + 库完整性闸门齐全（R42）"; exit 0; }
echo "修复：bash $W/tools/gw-start-guard.sh 统一拉起路径；升级后跑 db-integrity-gate.sh"
exit 1
