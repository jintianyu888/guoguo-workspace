#!/bin/bash
# activity-presage.sh —— 重启/备份前的预警（零 token，走果果主应用）
set -u
W=/home/j/.openclaw/workspace
CD=${1:-}
case "$CD" in
  restart)
    NOTIFY_ACCOUNT=default bash "$W/tools/notify.sh" "【预告】30 分钟后（08:00）是每日受控重启窗口：网关会有 1–2 分钟不可用，之后我立刻报「已恢复」。这不代表出故障。"
    python3 "$W/tools/activity.py" set kind=restart phase="即将重启（30 分钟内）" percent=0 note="08:00 窗口" >/dev/null 2>&1 || true
    ;;
  backup)
    NOTIFY_ACCOUNT=default bash "$W/tools/notify.sh" "【预告】10 分钟后开始每日全量备份（约 2–3 小时），期间机器会变慢，面板顶部会显示进度条。我会在过半和完成时各报一次。"
    ;;
esac
