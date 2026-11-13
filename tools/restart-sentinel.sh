#!/usr/bin/env bash
# restart-sentinel.sh —— 看护每日 08:00 重启窗口是否真的发生过
# 坑：date -d "… CST" 会把 CST 当美中部时间，偏 14h；改用 monotonic 反推
set -u
W=/home/j/.openclaw/workspace
THRESH=${1:-36}
LASTF=$W/state/restart-sentinel.last
today=$(date +%F)
msec=$(systemctl --user show openclaw-gateway -p ActiveEnterTimestampMonotonic --value 2>/dev/null)
if [ -z "$msec" ] || [ "$msec" = "0" ]; then echo "SENTINEL_UNKNOWN 服务无启动时间"; exit 2; fi
up=$(cut -d. -f1 /proc/uptime)
age_s=$(( up - msec / 1000000 ))
[ "$age_s" -lt 0 ] && age_s=0
age_h=$(( age_s / 3600 ))
lastwin=$(grep -E "重启窗口开始" "$W/state/work/restart-window.log" 2>/dev/null | tail -1)
lastwhy=$(tail -3 "$W/state/work/restart-window.log" 2>/dev/null | tr "\n" " | ")
if [ "$age_h" -lt "$THRESH" ]; then echo "SENTINEL_OK age=${age_h}h"; exit 0; fi
if [ -f "$LASTF" ] && [ "$(cat "$LASTF")" = "$today" ]; then echo "SENTINEL_ALERTED_TODAY age=${age_h}h"; exit 0; fi
echo "$today" > "$LASTF"
bash "$W/tools/notify.sh" "【重启看护】网关已连续 ${age_h} 小时未重启（阈值 ${THRESH}h），08:00 窗口可能一直被打回。最近窗口：${lastwin:-无}；尾部：${lastwhy}" 2>/dev/null || true
echo "SENTINEL_ALERTED age=${age_h}h"
