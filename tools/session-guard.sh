#!/usr/bin/env bash
# session-guard.sh —— 会话异常哨兵薄壳（2026-11-01 双审后落地，v1.1）
# 只读扫网关日志；阈值/去重逻辑在 session-guard.py
# 窗口 15 分钟 = cron 周期，避免重叠重复计数（双审 Must）
set -u
WS=${OPENCLAW_WS:-/home/j/.openclaw/workspace}
export OPENCLAW_WS="$WS"
UID_NUM=$(id -u)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$UID_NUM/bus}"
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH
has_window=0
for a in "$@"; do [ "$a" = "--window" ] && has_window=1; done
if [ "$has_window" = 0 ]; then
  exec /usr/bin/python3 "$WS/tools/session-guard.py" --window 15 "$@"
fi
exec /usr/bin/python3 "$WS/tools/session-guard.py" "$@"
