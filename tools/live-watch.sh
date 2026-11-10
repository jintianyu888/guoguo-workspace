#!/usr/bin/env bash
# live-watch.sh — 只为已有日志开一个黑窗实时显示（用于网关重启/系统单元这类由网关外跑的活）
# 用法: live-watch.sh <日志路径> "<标题>"
set -u
W=/home/j/.openclaw/workspace
LOG="${1:-}"; title="${2:-任务}"
[ -f "$LOG" ] || { echo "日志不存在: $LOG"; exit 64; }
ST="$W/state/work/live/status-watch.txt"; rm -f "$ST"
WP=$(wslpath -w "$LOG"); WPS=$(wslpath -w "$W/tools/live-tail.ps1"); WST=$(wslpath -w "$ST")
cd /mnt/c 2>/dev/null || true
/mnt/c/Windows/System32/cmd.exe /c start "果果 · $title" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WPS" -Log "$WP" -Title "$title" -Status "$WST" >/dev/null 2>&1
echo "已开窗：$title（日志 $LOG）"