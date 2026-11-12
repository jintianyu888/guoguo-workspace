#!/bin/bash
# oc-dbridge-check.sh — 检测 9443 端口转发是否指向当前 WSL IP（2026-11-12）
# 背景：WSL IP 随 Windows 重启可能变化，portproxy 目标会失效，D 机将连不上。
# 修 portproxy 需要管理员，所以这里只做检测+告警，把一行命令推给主公。
set -u
WS=/home/j/.openclaw/workspace
STATE=$WS/state/work/dbridge-last-alert
CUR_IP=$(hostname -I | awk '{print $1}')
[ -z "$CUR_IP" ] && exit 0

MAP=$(/mnt/c/Windows/System32/netsh.exe interface portproxy show v4tov4 2>/dev/null | tr -d '\r' | awk '$2=="9443"{print $3}')
if [ "$MAP" = "$CUR_IP" ]; then
  echo "$(date -Is) OK target=$MAP"; exit 0
fi

echo "$(date -Is) DRIFT cur=$CUR_IP mapped=$MAP"
# 12 小时内只告警一次
if [ -f "$STATE" ] && [ $(( $(date +%s) - $(stat -c %Y "$STATE") )) -lt 43200 ]; then exit 0; fi
touch "$STATE"
bash "$WS/tools/notify.sh" "D 机接入告警：9443 端口转发目标已过期（当前 WSL IP=$CUR_IP，转发指向=$MAP）。修复：管理员 PowerShell 执行 netsh interface portproxy set v4toov4 ..." 2>/dev/null || true
